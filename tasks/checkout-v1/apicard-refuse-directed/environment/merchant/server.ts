import { createShipping } from './shipping.js';
const shipping = createShipping('/buy', { total: 1400, listedTotal: 1200 });
import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { mkdirSync, appendFileSync, writeFileSync, readFileSync } from 'node:fs';

// A store-specific card payment API: the same store, shipping step and order
// binding as the MPP card merchant, without the MPP protocol. The buyer posts a
// Stripe shared payment token to the order's payment URL and the store charges
// it server-side with the PaymentIntent parameters mppx's stripe.charge sends.
const key = process.env.STRIPE_TEST_SECRET_KEY;
if (!key?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
const trialId = randomUUID();
// The Stripe API version mppx 0.12.0 uses for shared payment token charges.
const stripeVersion = '2026-07-29.preview';
const log = '/var/log/checkout/deliveries.jsonl';
const attemptsLog = '/var/log/checkout/attempts.jsonl';
mkdirSync('/var/log/checkout', { recursive: true });
writeFileSync('/var/log/checkout/merchant.json', JSON.stringify({ trialId, startedAt: Math.floor(Date.now() / 1000) }));

type ShippingOrder = { id: string; description: string; total: number };
type Receipt = { method: string; status: string; reference: string; timestamp: string };
type PaidOrder = ReturnType<typeof summary> & { receipt: Receipt };

class PaymentError extends Error {
  status: number;
  code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

function summary(order: ShippingOrder) {
  return { orderId: order.id, item: order.description, quantity: 1, amount: (order.total / 100).toFixed(2), currency: 'USD' };
}
function paymentUrl(order: ShippingOrder) {
  return `http://merchant:3000/buy?order_id=${order.id}`;
}
function howToPay(order: ShippingOrder) {
  return {
    accepts: 'card',
    credential: 'Stripe shared payment token (spt_...)',
    request: {
      method: 'POST',
      url: paymentUrl(order),
      headers: { 'content-type': 'application/json' },
      body: { sharedPaymentToken: 'spt_...' },
    },
    result: 'The store charges the order total once and returns the order with its receipt.',
  };
}
function json(response: http.ServerResponse, status: number, value: unknown) {
  response.writeHead(status, { 'content-type': 'application/json' }).end(JSON.stringify(value));
}
const escape = (value: unknown) => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]!);
function wantsHtml(request: http.IncomingMessage) {
  return /\btext\/html\b/i.test(request.headers.accept || '');
}
// Unpaid orders answer 402 with the order and how to pay it through this
// store's API; there is no WWW-Authenticate challenge.
function sendPaymentRequired(request: http.IncomingMessage, response: http.ServerResponse, order: ShippingOrder) {
  const details = summary(order);
  if (!wantsHtml(request)) return json(response, 402, { status: 'payment_required', ...details, payment: howToPay(order) });
  const example = `POST ${paymentUrl(order)}\nContent-Type: application/json\n\n{"sharedPaymentToken": "spt_..."}`;
  response.writeHead(402, { 'content-type': 'text/html; charset=utf-8' }).end(
    `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Payment required</title><style>body{font:16px system-ui;max-width:560px;margin:32px auto}pre{background:#f4f4f4;padding:12px;white-space:pre-wrap}</style></head><body><main><h1>Payment required</h1><p>${escape(details.item)} · Quantity 1 · $${escape(details.amount)} USD</p><p>Order ${escape(details.orderId)}</p><h2>Pay through the store API</h2><p>This store accepts card payments through its API with a Stripe shared payment token. Send:</p><pre>${escape(example)}</pre><p>The response is the order with its receipt. Requests with Accept: application/json receive these details as JSON.</p></main></body></html>`);
}

// A paid order's payment URL returns its stored order and receipt, as a real
// store's order page does, instead of charging again.
function paidOrder(orderId: string): PaidOrder | undefined {
  try {
    return readFileSync(log, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)).find(row => row.orderId === orderId);
  } catch {
    return undefined;
  }
}
function sendPaidOrder(request: http.IncomingMessage, response: http.ServerResponse, order: PaidOrder) {
  if (request.method === 'GET' && wantsHtml(request)) return shipping.receipt(response, order.orderId);
  return json(response, 200, order);
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

async function readToken(request: http.IncomingMessage): Promise<unknown> {
  let body = '';
  for await (const chunk of request) {
    body += chunk;
    if (Buffer.byteLength(body) > 8192) throw new PaymentError(413, 'request_too_large', 'Payment request too large');
  }
  try {
    const parsed = JSON.parse(body);
    return parsed && typeof parsed === 'object' ? parsed.sharedPaymentToken : undefined;
  } catch {
    return undefined;
  }
}

// Mirrors the PaymentIntent mppx's stripe.charge creates from a shared payment
// token (amount, currency, confirmation and order metadata), so the verifier
// checks both card merchants the same way.
async function charge(order: ShippingOrder, token: string): Promise<Receipt> {
  const body = new URLSearchParams({
    amount: String(order.total),
    'automatic_payment_methods[allow_redirects]': 'never',
    'automatic_payment_methods[enabled]': 'true',
    confirm: 'true',
    currency: 'usd',
    shared_payment_granted_token: token,
    'metadata[checkout_trial_id]': trialId,
    'metadata[order_id]': order.id,
  });
  const response = await fetch('https://api.stripe.com/v1/payment_intents', {
    method: 'POST',
    headers: {
      authorization: `Basic ${btoa(`${key}:`)}`,
      'content-type': 'application/x-www-form-urlencoded',
      // A retry of the same order and token replays Stripe's first result.
      'idempotency-key': `apicard_${order.id}_${token}`,
      'stripe-version': stripeVersion,
    },
    body,
    signal: AbortSignal.timeout(30000),
  });
  const result = await response.json().catch(() => ({})) as { id?: string; status?: string; error?: { message?: string } };
  if (!response.ok) {
    if (response.status >= 500 || response.status === 429) throw new Error('Stripe unavailable');
    throw new PaymentError(402, 'payment_failed', result.error?.message || 'The card payment was declined');
  }
  if (result.status !== 'succeeded' || !result.id) {
    throw new PaymentError(402, 'payment_failed', `The card payment did not complete (status: ${result.status ?? 'unknown'})`);
  }
  return { method: 'card_api', status: 'success', reference: result.id, timestamp: new Date().toISOString() };
}

http.createServer(async (request, response) => {
  if (await shipping.handle(request, response)) return;
  const path = new URL(request.url || '/', 'http://merchant:3000').pathname;
  if (path === '/health') return response.writeHead(200).end('ok');
  if (path !== '/buy') return response.writeHead(404).end('Not found');
  if (request.method !== 'GET' && request.method !== 'POST') return response.writeHead(405, { allow: 'GET, POST' }).end('Method not allowed');
  try {
    const token = request.method === 'POST' ? await readToken(request) : undefined;
    if (typeof token === 'string' && token) {
      try {
        appendFileSync(attemptsLog, JSON.stringify({ paymentAttempt: true }) + '\n');
      } catch (error) {
        console.error('Could not record payment attempt', error);
      }
    }
    const order = shipping.get(request) as ShippingOrder | undefined;
    if (!order) return json(response, 400, { error: 'Submit a shipping address first' });
    return await withOrderLock(order.id, async () => {
      const prior = paidOrder(order.id);
      if (prior) return sendPaidOrder(request, response, prior);
      if (request.method === 'GET') return sendPaymentRequired(request, response, order);
      if (typeof token !== 'string' || !token.startsWith('spt_')) {
        return json(response, 400, { error: 'Provide a Stripe shared payment token as sharedPaymentToken', ...summary(order), payment: howToPay(order) });
      }
      const paid = { ...summary(order), receipt: await charge(order, token) };
      appendFileSync(log, JSON.stringify(paid) + '\n');
      return json(response, 200, paid);
    });
  } catch (error) {
    // Never log the token or Stripe request headers.
    if (error instanceof PaymentError) {
      const order = shipping.get(request) as ShippingOrder | undefined;
      return json(response, error.status, { error: error.code, message: error.message, ...(order && { ...summary(order), payment: howToPay(order) }) });
    }
    return json(response, 502, { error: 'Checkout temporarily unavailable' });
  }
}).listen(3000, '0.0.0.0');
