import { createShipping } from './shipping.js';
const shipping = createShipping('/checkout');
import http from 'node:http';
import { mkdirSync, appendFileSync } from 'node:fs';

const key = process.env.STRIPE_TEST_SECRET_KEY;
if (!key?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
const base = process.env.PUBLIC_BASE_URL || 'http://merchant:3000';
const log = '/var/log/checkout/sessions.jsonl';
mkdirSync('/var/log/checkout', { recursive: true });

const page = `<!doctype html><html><head><meta charset="utf-8"><title>Notebook Store</title></head>
<body><main><h1>Tempo Notebook</h1><p>One notebook · $12.00</p>
<form method="post" action="/checkout"><button>Buy notebook</button></form></main></body></html>`;

http.createServer(async (request, response) => {
  if (await shipping.handle(request, response)) return;
  if (request.url === '/health') {
    response.writeHead(200).end('ok');
    return;
  }
  if (request.url === '/' && request.method === 'GET') {
    response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(page);
    return;
  }
  if (new URL(request.url, 'http://merchant:3000').pathname === '/checkout' && ['GET', 'POST'].includes(request.method)) {
    const shippingOrder = shipping.get(request);
    if (!shippingOrder) return response.writeHead(400).end('Submit a shipping address first');
    const orderId = shippingOrder.id;
    const form = new URLSearchParams({
      mode: 'payment',
      'payment_method_types[0]': 'crypto',
      client_reference_id: orderId,
      'metadata[order_id]': orderId,
      'line_items[0][price_data][currency]': 'usd',
      'line_items[0][price_data][unit_amount]': '1200',
      'line_items[0][price_data][product_data][name]': 'Tempo Notebook',
      'line_items[0][quantity]': '1',
      success_url: `${base}/complete?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${base}/`,
    });
    try {
      const stripe = await fetch('https://api.stripe.com/v1/checkout/sessions', {
        method: 'POST',
        headers: { authorization: `Bearer ${key}`, 'content-type': 'application/x-www-form-urlencoded' },
        body: form,
        signal: AbortSignal.timeout(30000),
      });
      const session = await stripe.json();
      if (!stripe.ok || !session.id?.startsWith('cs_test_') || !session.url) {
        throw new Error(`Stripe session creation failed: ${stripe.status}`);
      }
      appendFileSync(log, JSON.stringify({ orderId, sessionId: session.id }) + '\n');
      response.writeHead(303, { location: session.url }).end();
    } catch (error) {
      console.error(error);
      response.writeHead(502).end('Checkout temporarily unavailable');
    }
    return;
  }
  if (request.url?.startsWith('/complete') && request.method === 'GET') {
    return shipping.stripeReceipt(request, response, 'sessions');
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
