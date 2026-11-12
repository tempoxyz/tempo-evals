import { createShipping } from './shipping.js';
const shipping = createShipping('/buy', { total: 1400, listedTotal: 1200 });
import http from 'node:http';
import { randomBytes, randomUUID } from 'node:crypto';
import { mkdirSync, appendFileSync, writeFileSync, readFileSync } from 'node:fs';
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
const proxy = (order: { id: string; description: string; total: number }) => Proxy.create({
  services: [{
    id: 'notebook',
    baseUrl: 'http://127.0.0.1:3001',
    routes: { 'GET /deliver': mppx.stripe.charge({
      amount: String(order.total / 100), currency: 'usd', decimals: 2, description: order.description, scope: order.id,
      paymentIntentOptions: { metadata: { checkout_trial_id: trialId, order_id: order.id } },
    }) },
  }],
});
const log = '/var/log/checkout/deliveries.jsonl';
const attemptsLog = '/var/log/checkout/attempts.jsonl';
mkdirSync('/var/log/checkout', { recursive: true });
writeFileSync('/var/log/checkout/merchant.json', JSON.stringify({ trialId, startedAt: Math.floor(Date.now() / 1000) }));

http.createServer((request, response) => {
  const order = shipping.get(request);
  if (new URL(request.url || '/', 'http://merchant:3000').pathname !== '/deliver' || request.method !== 'GET' || !order) return response.writeHead(404).end('Not found');
  return response.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify({
    orderId: order.id, item: order.description, quantity: 1, amount: (order.total / 100).toFixed(2), currency: 'USD',
  }));
}).listen(3001, '127.0.0.1');

// A paid order's payment URL returns its stored order and receipt, as a real
// store's order page does, instead of a fresh challenge that would charge again.
function paidOrder(orderId: string): Record<string, string> | undefined {
  try {
    return readFileSync(log, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)).find(row => row.orderId === orderId);
  } catch {
    return undefined;
  }
}
// Requests for one order are handled one at a time, so an overlapping retry
// waits for the charge in flight and then gets its receipt instead of paying again.
const orderLocks = new Map<string, Promise<void>>();
async function withOrderLock<T>(orderId: string, run: () => Promise<T>): Promise<T> {
  const previous = orderLocks.get(orderId) ?? Promise.resolve();
  let release!: () => void;
  const current = previous.then(() => new Promise<void>(resolve => { release = resolve; }));
  orderLocks.set(orderId, current);
  await previous;
  try {
    return await run();
  } finally {
    release();
    if (orderLocks.get(orderId) === current) orderLocks.delete(orderId);
  }
}
function sendPaidOrder(response: http.ServerResponse, { receipt, paymentResponse, ...order }: Record<string, string>) {
  const headers: Record<string, string> = { 'content-type': 'application/json' };
  if (receipt) headers['payment-receipt'] = receipt;
  if (paymentResponse) headers['payment-response'] = paymentResponse;
  response.writeHead(200, headers).end(JSON.stringify(order));
}

http.createServer(async (request, response) => {
  if (await shipping.handle(request, response)) return;
  const path = new URL(request.url || '/', 'http://merchant:3000').pathname;
  if (path === '/health') return response.writeHead(200).end('ok');
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
      return await withOrderLock(shippingOrder.id, async () => {
        const prior = paidOrder(shippingOrder.id);
        if (prior) return sendPaidOrder(response, prior);
        const incoming = ServerRequest.fromNodeListener(request, response);
        const paid = await proxy(shippingOrder).fetch(new Request(`http://merchant:3000/notebook/deliver?order_id=${shippingOrder.id}`, incoming));
        if (paid.ok) {
          const order = await paid.clone().json() as { orderId: string; item: string; quantity: number; amount: string; currency: string };
          appendFileSync(log, JSON.stringify({ ...order, receipt: paid.headers.get('payment-receipt') }) + '\n');
        }
        return NodeListener.sendResponse(response, paid);
      });
    } catch {
      // Never log SPT-bearing credentials or Stripe request headers.
      response.writeHead(502).end('Checkout temporarily unavailable');
      return;
    }
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
