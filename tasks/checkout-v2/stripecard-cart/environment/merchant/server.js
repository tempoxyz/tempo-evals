import { createShipping } from './shipping.js';
const shipping = createShipping('/checkout');
import http from 'node:http';
import { mkdirSync, appendFileSync, readFileSync } from 'node:fs';

const key = process.env.STRIPE_TEST_SECRET_KEY;
if (!key?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
const base = process.env.PUBLIC_BASE_URL || 'http://merchant:3000';
const log = '/var/log/checkout/sessions.jsonl';
mkdirSync('/var/log/checkout', { recursive: true });
let records = [];
try { records = readFileSync(log, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
// The latest Checkout Session per order; reopening the payment URL reuses it.
const sessions = new Map(records.map(record => [record.orderId, record.sessionId]));
const pending = new Map();

async function stripe(path, body) {
  const response = await fetch(`https://api.stripe.com/v1${path}`, {
    method: body ? 'POST' : 'GET',
    headers: { authorization: `Bearer ${key}`, 'content-type': 'application/x-www-form-urlencoded' },
    body,
    signal: AbortSignal.timeout(30000),
  });
  const session = await response.json();
  if (!response.ok || session.livemode !== false || !session.id?.startsWith('cs_test_')) {
    throw new Error(`Stripe session request failed: ${response.status}`);
  }
  return session;
}

http.createServer(async (request, response) => {
  if (await shipping.handle(request, response)) return;
  if (request.url === '/health') {
    response.writeHead(200).end('ok');
    return;
  }
  if (new URL(request.url, 'http://merchant:3000').pathname === '/checkout' && ['GET', 'POST'].includes(request.method)) {
    const shippingOrder = shipping.get(request);
    if (!shippingOrder) return response.writeHead(400).end('Submit a shipping address first');
    const orderId = shippingOrder.id;
    const form = new URLSearchParams({
      mode: 'payment',
      'payment_method_types[0]': 'card',
      'wallet_options[link][display]': 'never',
      client_reference_id: orderId,
      'metadata[order_id]': orderId,
      'line_items[0][price_data][currency]': 'usd',
      'line_items[0][price_data][unit_amount]': String(shippingOrder.total),
      'line_items[0][price_data][product_data][name]': shippingOrder.description,
      'line_items[0][quantity]': '1',
      success_url: `${base}/complete?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${base}/`,
    });
    try {
      let operation = pending.get(orderId);
      if (!operation) {
        operation = (async () => {
          const existing = sessions.get(orderId);
          if (existing) {
            const session = await stripe(`/checkout/sessions/${existing}`);
            // A paid order keeps its receipt and an open session stays payable;
            // only an expired session is replaced.
            if (session.payment_status === 'paid' || (session.status === 'open' && session.url)) return session;
          }
          const session = await stripe('/checkout/sessions', form);
          if (!session.url) throw new Error('Stripe session creation returned no URL');
          appendFileSync(log, JSON.stringify({ orderId, sessionId: session.id }) + '\n');
          sessions.set(orderId, session.id);
          return session;
        })().finally(() => pending.delete(orderId));
        pending.set(orderId, operation);
      }
      const session = await operation;
      if (session.payment_status === 'paid') return shipping.receipt(response, orderId);
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
