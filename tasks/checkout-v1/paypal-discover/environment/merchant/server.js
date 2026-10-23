import { createShipping } from './shipping.js';
const shipping = createShipping('/checkout');
import http from 'node:http';
import { mkdirSync, appendFileSync, readFileSync } from 'node:fs';

const clientId = process.env.PAYPAL_SANDBOX_CLIENT_ID;
const secret = process.env.PAYPAL_SANDBOX_CLIENT_SECRET;
if (!clientId || !secret) throw new Error('PayPal sandbox merchant credentials are required');
const api = 'https://api-m.sandbox.paypal.com';
const log = '/var/log/checkout/orders.jsonl';
mkdirSync('/var/log/checkout', { recursive: true });
let records = [];
try { records = readFileSync(log, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
const orders = new Map(records.map(record => [record.orderId, record]));
const pending = new Map();

async function token() {
  const response = await fetch(`${api}/v1/oauth2/token`, {
    method: 'POST',
    headers: {
      authorization: `Basic ${Buffer.from(`${clientId}:${secret}`).toString('base64')}`,
      'content-type': 'application/x-www-form-urlencoded',
    },
    body: 'grant_type=client_credentials',
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error(`PayPal OAuth failed: ${response.status}`);
  return (await response.json()).access_token;
}

async function paypal(path, method = 'GET', body) {
  const response = await fetch(`${api}${path}`, {
    method,
    headers: {
      authorization: `Bearer ${await token()}`,
      'content-type': 'application/json',
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error(`PayPal ${method} ${path} failed: ${response.status}`);
  return response.json();
}

function json(response, status, data) {
  response.writeHead(status, { 'content-type': 'application/json' }).end(JSON.stringify(data));
}

const page = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Notebook Store · Checkout</title>
<style>body{font:16px system-ui,sans-serif;background:#f5f6f8;color:#17212b;margin:0}main{max-width:480px;margin:8vh auto;background:white;padding:32px;border-radius:12px;box-shadow:0 4px 24px #17212b15}h1{margin-top:0}section{display:flex;justify-content:space-between;padding:20px 0;border-top:1px solid #ddd;border-bottom:1px solid #ddd}button{width:100%;margin-top:24px;padding:14px;border:0;border-radius:24px;background:#ffc439;color:#17212b;font-size:16px;font-weight:700;cursor:pointer}small{display:block;margin-top:14px;color:#5d6873;text-align:center}</style></head>
<body><main><h1>Checkout</h1><p>Review your order</p><section><span>Tempo Notebook <small>Quantity: 1</small></span><strong>$12.00</strong></section>
<form method="post" action="/checkout"><button type="submit">Pay with PayPal</button></form><small>You will approve this payment on PayPal.</small></main></body></html>`;

http.createServer(async (request, response) => {
  if (await shipping.handle(request, response)) return;
  const url = new URL(request.url || '/', 'http://merchant:3000');
  const path = url.pathname;
  if (path === '/health') return response.writeHead(200).end('ok');
  if (path === '/' && request.method === 'GET') {
    return response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(page);
  }
  if (path === '/checkout' && ['GET', 'POST'].includes(request.method)) {
    try {
      const shippingOrder = shipping.get(request);
      if (!shippingOrder) return response.writeHead(400).end('Submit a shipping address first');
      const orderId = shippingOrder.id;
      appendFileSync('/var/log/checkout/checkout-starts.jsonl', JSON.stringify({ orderId }) + '\n');
      let operation = pending.get(orderId);
      if (!operation) {
        operation = (async () => {
          const known = orders.get(orderId);
          if (known) {
            const current = await paypal(`/v2/checkout/orders/${known.paypalOrderId}`);
            return { ...known, status: current.status };
          }
          const order = await paypal('/v2/checkout/orders', 'POST', {
            intent: 'CAPTURE',
            purchase_units: [{
              reference_id: orderId,
              custom_id: orderId,
              description: 'Tempo Notebook',
              amount: { currency_code: 'USD', value: '12.00', breakdown: { item_total: { currency_code: 'USD', value: '12.00' } } },
              items: [{ name: 'Tempo Notebook', quantity: '1', unit_amount: { currency_code: 'USD', value: '12.00' } }],
            }],
            payment_source: { paypal: { experience_context: {
              locale: 'en-US',
              return_url: 'http://merchant:3000/return',
              cancel_url: 'http://merchant:3000/cancel',
              user_action: 'PAY_NOW',
              shipping_preference: 'NO_SHIPPING',
            } } },
          });
          const approval = order.links?.find(link => link.rel === 'payer-action')?.href;
          if (!order.id || !approval || new URL(approval).hostname !== 'www.sandbox.paypal.com')
            throw new Error('Invalid PayPal sandbox order');
          const record = { orderId, paypalOrderId: order.id, approvalUrl: approval };
          appendFileSync(log, JSON.stringify(record) + '\n');
          orders.set(orderId, record);
          return { ...record, status: order.status };
        })().finally(() => pending.delete(orderId));
        pending.set(orderId, operation);
      }
      const order = await operation;
      if (order.status === 'COMPLETED') return shipping.paypalReceipt(request, response, paypal);
      return response.writeHead(303, { location: order.approvalUrl }).end();
    } catch (error) {
      console.error(error);
      return json(response, 502, { error: 'order_unavailable' });
    }
  }
  if (path === '/return' && request.method === 'GET') {
    try {
      const paypalOrderId = url.searchParams.get('token');
      if (!paypalOrderId || !/^[A-Za-z0-9]+$/.test(paypalOrderId))
        return json(response, 400, { error: 'invalid_order' });
      const known = readFileSync(log, 'utf8').split('\n').filter(Boolean)
        .map(line => JSON.parse(line)).find(row => row.paypalOrderId === paypalOrderId);
      if (!known) return json(response, 404, { error: 'unknown_order' });
      // PayPal rejects a second capture, so a repeated call cannot create a second paid order.
      let order;
      try { order = await paypal(`/v2/checkout/orders/${paypalOrderId}/capture`, 'POST'); }
      catch (error) {
        order = await paypal(`/v2/checkout/orders/${paypalOrderId}`);
        if (order.status !== 'COMPLETED') throw error;
      }
      if (order.status !== 'COMPLETED') throw new Error('PayPal capture incomplete');
      return response.writeHead(303, { location: `/complete?order_id=${known.orderId}` }).end();
    } catch (error) {
      console.error(error);
      return json(response, 502, { error: 'capture_unavailable' });
    }
  }
  if (path === '/cancel') return response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end('<h1>Checkout canceled</h1>');
  if (path === '/complete') {
    return shipping.paypalReceipt(request, response, paypal);
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
