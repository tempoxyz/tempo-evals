import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { mkdirSync, appendFileSync, readFileSync } from 'node:fs';

const clientId = process.env.PAYPAL_SANDBOX_CLIENT_ID;
const secret = process.env.PAYPAL_SANDBOX_CLIENT_SECRET;
if (!clientId || !secret) throw new Error('PayPal sandbox merchant credentials are required');
const api = 'https://api-m.sandbox.paypal.com';
const log = '/var/log/checkout/orders.jsonl';
mkdirSync('/var/log/checkout', { recursive: true });

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

const page = `<!doctype html><html><head><meta charset="utf-8"><title>Notebook Store</title></head>
<body><main><h1>Tempo Notebook</h1><p>One notebook · $12.00</p><div id="paypal-button"></div>
<p id="status" role="status"></p></main>
<script src="https://www.paypal.com/sdk/js?client-id=${encodeURIComponent(clientId)}&currency=USD&components=buttons"></script>
<script>
paypal.Buttons({
  fundingSource: paypal.FUNDING.PAYPAL,
  createOrder: async () => {
    const response = await fetch('/api/orders', { method: 'POST' });
    if (!response.ok) throw new Error('Could not create order');
    return (await response.json()).id;
  },
  onApprove: async data => {
    const response = await fetch('/api/orders/' + encodeURIComponent(data.orderID) + '/capture', { method: 'POST' });
    if (!response.ok) throw new Error('Could not capture order');
    location.href = '/complete';
  },
  onError: () => { document.getElementById('status').textContent = 'Checkout temporarily unavailable'; },
}).render('#paypal-button');
</script></body></html>`;

http.createServer(async (request, response) => {
  const path = new URL(request.url || '/', 'http://merchant:3000').pathname;
  if (path === '/health') return response.writeHead(200).end('ok');
  if (path === '/' && request.method === 'GET') {
    return response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(page);
  }
  if (path === '/api/orders' && request.method === 'POST') {
    try {
      const orderId = randomUUID();
      const order = await paypal('/v2/checkout/orders', 'POST', {
        intent: 'CAPTURE',
        purchase_units: [{
          reference_id: orderId,
          custom_id: orderId,
          description: 'Tempo Notebook',
          amount: { currency_code: 'USD', value: '12.00', breakdown: { item_total: { currency_code: 'USD', value: '12.00' } } },
          items: [{ name: 'Tempo Notebook', quantity: '1', unit_amount: { currency_code: 'USD', value: '12.00' } }],
        }],
      });
      if (!order.id || order.status !== 'CREATED') throw new Error('Invalid PayPal sandbox order');
      appendFileSync(log, JSON.stringify({ orderId, paypalOrderId: order.id }) + '\n');
      return json(response, 200, { id: order.id });
    } catch (error) {
      console.error(error);
      return json(response, 502, { error: 'order_unavailable' });
    }
  }
  const match = /^\/api\/orders\/([A-Za-z0-9]+)\/capture$/.exec(path);
  if (match && request.method === 'POST') {
    try {
      const known = readFileSync(log, 'utf8').split('\n').filter(Boolean)
        .some(line => JSON.parse(line).paypalOrderId === match[1]);
      if (!known) return json(response, 404, { error: 'unknown_order' });
      // PayPal rejects a second capture, so a repeated call cannot create a second paid order.
      const order = await paypal(`/v2/checkout/orders/${match[1]}/capture`, 'POST');
      return json(response, order.status === 'COMPLETED' ? 200 : 502, { status: order.status });
    } catch (error) {
      console.error(error);
      return json(response, 502, { error: 'capture_unavailable' });
    }
  }
  if (path === '/complete') {
    return response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end('<h1>Order received</h1><p>Payment is being verified.</p>');
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
