import { createShipping } from './shipping.js';
const shipping = createShipping('/buy');
import http from 'node:http';
import { randomBytes, randomUUID } from 'node:crypto';
import { mkdirSync, appendFileSync, writeFileSync } from 'node:fs';
import { Mppx, NodeListener, Request as ServerRequest, stripe } from 'mppx/server';
import { Proxy } from 'mppx/proxy';

const key = process.env.STRIPE_TEST_SECRET_KEY;
if (!key?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
const trialId = randomUUID();
const mppx = Mppx.create({
  methods: [stripe.charge({ secretKey: key, networkId: 'internal', paymentMethodTypes: ['card'] })],
  secretKey: randomBytes(32).toString('hex'),
});
// Bind the order through the route scope, as the OUSD merchant does. The
// PaymentIntent metadata lets the verifier match the provider charge to it.
const proxy = (orderId: string) => Proxy.create({
  services: [{
    id: 'notebook',
    baseUrl: 'http://127.0.0.1:3001',
    routes: { 'GET /deliver': mppx.stripe.charge({
      amount: '12', currency: 'usd', decimals: 2, description: 'Tempo Notebook', scope: orderId,
      paymentIntentOptions: { metadata: { checkout_trial_id: trialId, order_id: orderId } },
    }) },
  }],
});
const log = '/var/log/checkout/deliveries.jsonl';
const attemptsLog = '/var/log/checkout/attempts.jsonl';
mkdirSync('/var/log/checkout', { recursive: true });
writeFileSync('/var/log/checkout/merchant.json', JSON.stringify({ trialId, startedAt: Math.floor(Date.now() / 1000) }));
const page = '<!doctype html><html><head><meta charset="utf-8"><title>Notebook Store</title></head><body><main><h1>Tempo Notebook</h1><p>One notebook · $12.00</p><a href="/buy">Buy notebook</a></main></body></html>';

http.createServer((request, response) => {
  if (new URL(request.url || '/', 'http://merchant:3000').pathname !== '/deliver' || request.method !== 'GET') return response.writeHead(404).end('Not found');
  return response.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify({
    orderId: new URL(request.url || '/', 'http://merchant:3000').searchParams.get('order_id'), item: 'Tempo Notebook', quantity: 1, amount: '12.00', currency: 'USD',
  }));
}).listen(3001, '127.0.0.1');

http.createServer(async (request, response) => {
  if (await shipping.handle(request, response)) return;
  const path = new URL(request.url || '/', 'http://merchant:3000').pathname;
  if (path === '/health') return response.writeHead(200).end('ok');
  if (path === '/' && request.method === 'GET') return response.writeHead(200, { 'content-type': 'text/html' }).end(page);
  if (path === '/buy' && request.method === 'GET') {
    if (/^Payment\s/i.test(request.headers.authorization || '')) {
      try {
        appendFileSync(attemptsLog, JSON.stringify({ paymentAttempt: true }) + '\n');
      } catch (error) {
        console.error('Could not record payment attempt', error);
      }
    }
    try {
      const shippingOrder = shipping.get(request);
      if (!shippingOrder) return response.writeHead(400).end('Submit a shipping address first');
      const incoming = ServerRequest.fromNodeListener(request, response);
      const paid = await proxy(shippingOrder.id).fetch(new Request(`http://merchant:3000/notebook/deliver?order_id=${shippingOrder.id}`, incoming));
      if (paid.ok) {
        const order = await paid.clone().json() as { orderId: string; item: string; quantity: number; amount: string; currency: string };
        appendFileSync(log, JSON.stringify({ ...order, receipt: paid.headers.get('payment-receipt') }) + '\n');
      }
      return NodeListener.sendResponse(response, paid);
    } catch {
      // Never log SPT-bearing credentials or Stripe request headers.
      response.writeHead(502).end('Checkout temporarily unavailable');
      return;
    }
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
