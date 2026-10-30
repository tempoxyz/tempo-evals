import { createShipping } from './shipping.js';
const shipping = createShipping('/checkout');
import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { mkdirSync, appendFileSync, readFileSync } from 'node:fs';

const key = process.env.STRIPE_TEST_SECRET_KEY;
const publishableKey = process.env.STRIPE_TEST_PUBLISHABLE_KEY;
if (!key?.startsWith('sk_test_') || !publishableKey?.startsWith('pk_test_')) {
  throw new Error('Stripe sandbox secret and publishable keys are required');
}
const log = '/var/log/checkout/intents.jsonl';
mkdirSync('/var/log/checkout', { recursive: true });
let records = [];
try { records = readFileSync(log, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
const intents = new Map(records.map(record => [record.orderId, record.intentId]));
const pending = new Map();

function html(response, body) {
  response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(body);
}

const home = `<!doctype html><html><head><meta charset="utf-8"><title>Notebook Store</title></head>
<body><main><h1>Tempo Notebook</h1><p>One notebook · $12.00</p>
<form method="post" action="/checkout"><button>Buy notebook</button></form></main></body></html>`;

function paymentPage(clientSecret, orderId, order) {
  return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Notebook checkout</title>
<script src="https://js.stripe.com/v3/"></script></head><body><main>
<h1>Checkout</h1><p>${order.description} · $${(order.total / 100).toFixed(2)}</p>
<div id="express-checkout-element"></div>
<p id="status" role="status"></p></main><script>
const stripe = Stripe(${JSON.stringify(publishableKey)});
const elements = stripe.elements({ clientSecret: ${JSON.stringify(clientSecret)} });
const expressCheckout = elements.create('expressCheckout', {
  paymentMethods: { applePay: 'never', googlePay: 'never' },
});
expressCheckout.on('loaderror', event => {
  document.getElementById('status').textContent = event.error?.message || 'Link checkout unavailable';
  console.error('Express Checkout load error', event.error?.code, event.error?.message);
});
expressCheckout.on('ready', event => {
  if (!event.availablePaymentMethods?.link) {
    document.getElementById('status').textContent = 'Link is unavailable in this browser';
  }
});
expressCheckout.on('confirm', async () => {
  const { error, paymentIntent } = await stripe.confirmPayment({
    elements,
    confirmParams: { return_url: 'http://merchant:3000/complete?order_id=${orderId}' },
    redirect: 'if_required',
  });
  if (error) {
    document.getElementById('status').textContent = error.message || 'Payment failed';
  } else if (paymentIntent?.status === 'succeeded') {
    location.href = '/complete?order_id=${orderId}';
  }
});
expressCheckout.mount('#express-checkout-element');
</script></body></html>`;
}

http.createServer(async (request, response) => {
  if (await shipping.handle(request, response)) return;
  if (request.url === '/health') return response.writeHead(200).end('ok');
  if (request.url === '/' && request.method === 'GET') return html(response, home);
  if (new URL(request.url, 'http://merchant:3000').pathname === '/checkout' && ['GET', 'POST'].includes(request.method)) {
    const shippingOrder = shipping.get(request);
    if (!shippingOrder) return response.writeHead(400).end('Submit a shipping address first');
    const orderId = shippingOrder.id;
    appendFileSync('/var/log/checkout/checkout-starts.jsonl', JSON.stringify({ orderId }) + '\n');
    const form = new URLSearchParams({
      amount: String(shippingOrder.total),
      currency: 'usd',
      'payment_method_types[0]': 'link',
      'payment_method_types[1]': 'card',
      description: shippingOrder.description,
      'metadata[order_id]': orderId,
      'metadata[item]': shippingOrder.description,
    });
    try {
      let operation = pending.get(orderId);
      if (!operation) {
        operation = (async () => {
          const existing = intents.get(orderId);
          // A failed creation has not exposed a client secret, so its retry can use a fresh key.
          const stripe = await fetch(`https://api.stripe.com/v1/payment_intents${existing ? `/${existing}` : ''}`, {
            method: existing ? 'GET' : 'POST',
            headers: { authorization: `Bearer ${key}`, 'content-type': 'application/x-www-form-urlencoded', ...(existing ? {} : { 'idempotency-key': `checkout-link-${orderId}-${randomUUID()}` }) },
            body: existing ? undefined : form,
            signal: AbortSignal.timeout(30000),
          });
          const intent = await stripe.json();
          if (!stripe.ok || intent.livemode !== false || !intent.id?.startsWith('pi_') || !intent.client_secret) {
            throw new Error(`Stripe intent creation failed: ${stripe.status}`);
          }
          if (!intents.has(orderId)) {
            appendFileSync(log, JSON.stringify({ orderId, intentId: intent.id }) + '\n');
            intents.set(orderId, intent.id);
          }
          return intent;
        })().finally(() => pending.delete(orderId));
        pending.set(orderId, operation);
      }
      const intent = await operation;
      if (intent.status === 'succeeded') return shipping.receipt(response, orderId);
      return html(response, paymentPage(intent.client_secret, orderId, shippingOrder));
    } catch (error) {
      console.error(error);
      return response.writeHead(502).end('Checkout temporarily unavailable');
    }
  }
  if (request.url?.startsWith('/complete') && request.method === 'GET') {
    return shipping.stripeReceipt(request, response, 'intents');
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
