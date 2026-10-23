import { createShipping } from './shipping.js';
const shipping = createShipping('/buy');
import http from 'node:http';
import { randomBytes, randomUUID } from 'node:crypto';
import { mkdirSync, appendFileSync, writeFileSync } from 'node:fs';
import { Mppx, NodeListener, Request as ServerRequest, stripe } from 'mppx/server';

const key = process.env.STRIPE_TEST_SECRET_KEY;
if (!key?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
const dir = '/var/log/checkout';
const orderId = randomUUID();
const trialId = randomUUID();
mkdirSync(dir, { recursive: true });
writeFileSync(`${dir}/merchant.json`, JSON.stringify({ orderId, trialId, startedAt: Math.floor(Date.now() / 1000) }));
const mppx = Mppx.create({
  methods: [stripe.charge({ secretKey: key, networkId: 'internal', paymentMethodTypes: ['card'] })],
  secretKey: randomBytes(32).toString('hex'),
});
const charge = (orderId: string) => mppx.stripe.charge({
  amount: '12', currency: 'usd', decimals: 2, description: 'Tempo Notebook', externalId: orderId,
  paymentIntentOptions: { metadata: { checkout_trial_id: trialId, order_id: orderId } },
});
const page = '<!doctype html><html><head><meta charset="utf-8"><title>Notebook Store</title></head><body><main><h1>Tempo Notebook</h1><p>One notebook · $12.00</p><a href="/buy">Buy notebook</a></main></body></html>';

http.createServer(async (request, response) => {
  if (await shipping.handle(request, response)) return;
  const path = new URL(request.url || '/', 'http://merchant:3000').pathname;
  if (path === '/health') return response.writeHead(200).end('ok');
  if (path === '/' && request.method === 'GET') return response.writeHead(200, { 'content-type': 'text/html' }).end(page);
  if (path === '/buy' && request.method === 'GET') {
    try {
      if (/^Payment\s/i.test(request.headers.authorization || '')) {
        appendFileSync(`${dir}/attempts.jsonl`, JSON.stringify({ paymentAttempt: true }) + '\n');
      }
      const shippingOrder = shipping.get(request);
      if (!shippingOrder) return response.writeHead(400).end('Submit a shipping address first');
      const orderId = shippingOrder.id;
      const paid = await charge(orderId)(ServerRequest.fromNodeListener(request, response));
      if (paid.status === 402) return NodeListener.sendResponse(response, paid.challenge);
      const order = { orderId, shipping: shippingOrder.shipping, item: 'Tempo Notebook', quantity: 1, amount: '12.00', currency: 'USD' };
      const result = paid.withReceipt(Response.json(order));
      appendFileSync(`${dir}/deliveries.jsonl`, JSON.stringify({ ...order, receipt: result.headers.get('payment-receipt') }) + '\n');
      return NodeListener.sendResponse(response, result);
    } catch {
      // Never log SPT-bearing credentials or Stripe request headers.
      response.writeHead(502).end('Checkout temporarily unavailable');
      return;
    }
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
