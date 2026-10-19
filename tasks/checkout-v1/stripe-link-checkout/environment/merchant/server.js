import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { mkdirSync, appendFileSync } from 'node:fs';

const key = process.env.STRIPE_TEST_SECRET_KEY;
const publishableKey = process.env.STRIPE_TEST_PUBLISHABLE_KEY;
if (!key?.startsWith('sk_test_') || !publishableKey?.startsWith('pk_test_')) {
  throw new Error('Stripe sandbox secret and publishable keys are required');
}
const log = '/var/log/checkout/intents.jsonl';
mkdirSync('/var/log/checkout', { recursive: true });

function html(response, body) {
  response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(body);
}

const home = `<!doctype html><html><head><meta charset="utf-8"><title>Notebook Store</title></head>
<body><main><h1>Tempo Notebook</h1><p>One notebook · $12.00</p>
<form method="post" action="/checkout"><button>Buy notebook</button></form></main></body></html>`;

function paymentPage(clientSecret) {
  return `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Notebook checkout</title>
<script src="https://js.stripe.com/v3/"></script></head><body><main>
<h1>Tempo Notebook</h1><p>One notebook · $12.00</p>
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
    confirmParams: { return_url: 'http://merchant:3000/complete' },
    redirect: 'if_required',
  });
  if (error) {
    document.getElementById('status').textContent = error.message || 'Payment failed';
  } else if (paymentIntent?.status === 'succeeded') {
    location.href = '/complete';
  }
});
expressCheckout.mount('#express-checkout-element');
</script></body></html>`;
}

http.createServer(async (request, response) => {
  if (request.url === '/health') return response.writeHead(200).end('ok');
  if (request.url === '/' && request.method === 'GET') return html(response, home);
  if (request.url === '/checkout' && request.method === 'POST') {
    const orderId = randomUUID();
    const form = new URLSearchParams({
      amount: '1200',
      currency: 'usd',
      'payment_method_types[0]': 'link',
      'payment_method_types[1]': 'card',
      description: 'Tempo Notebook',
      'metadata[order_id]': orderId,
      'metadata[item]': 'Tempo Notebook',
    });
    try {
      const stripe = await fetch('https://api.stripe.com/v1/payment_intents', {
        method: 'POST',
        headers: { authorization: `Bearer ${key}`, 'content-type': 'application/x-www-form-urlencoded' },
        body: form,
        signal: AbortSignal.timeout(30000),
      });
      const intent = await stripe.json();
      if (!stripe.ok || intent.livemode !== false || !intent.id?.startsWith('pi_') || !intent.client_secret) {
        throw new Error(`Stripe intent creation failed: ${stripe.status}`);
      }
      appendFileSync(log, JSON.stringify({ orderId, intentId: intent.id }) + '\n');
      return html(response, paymentPage(intent.client_secret));
    } catch (error) {
      console.error(error);
      return response.writeHead(502).end('Checkout temporarily unavailable');
    }
  }
  if (request.url?.startsWith('/complete') && request.method === 'GET') {
    return html(response, '<!doctype html><title>Order received</title><h1>Order received</h1><p>Payment is being verified.</p>');
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
