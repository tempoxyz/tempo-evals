import http from 'node:http';
import { randomBytes, randomUUID } from 'node:crypto';
import { mkdirSync, appendFileSync, writeFileSync } from 'node:fs';
import { Mppx, NodeListener, Request as ServerRequest, evm } from 'mppx/server';

const recipient = process.env.X402_RECIPIENT_ADDRESS as `0x${string}`;
if (!/^0x[0-9a-fA-F]{40}$/.test(recipient || '')) throw new Error('A Base Sepolia recipient address is required');
const stripeKey = process.env.STRIPE_TEST_SECRET_KEY;
if (!stripeKey?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
const usdc = evm.assets.baseSepolia.USDC.address;
const mppx = Mppx.create({
  methods: [evm.charge({
    currency: evm.assets.baseSepolia.USDC,
    recipient,
    x402: { facilitator: process.env.X402_FACILITATOR_URL || 'https://x402.org/facilitator' },
  })],
  secretKey: randomBytes(32).toString('hex'),
});
const dir = '/var/log/checkout';
mkdirSync(dir, { recursive: true });
writeFileSync(`${dir}/merchant.json`, JSON.stringify({ recipient, usdc }));
const page = '<!doctype html><html><head><meta charset="utf-8"><title>Notebook Store</title></head><body><main><h1>Tempo Notebook</h1><p>One notebook · $12.00</p><a href="/buy">Buy notebook</a></main></body></html>';

http.createServer(async (request, response) => {
  if (request.url !== '/deliver' || request.method !== 'GET') return response.writeHead(404).end('Not found');
  try {
    const orderId = randomUUID();
    const card = await fetch('https://api.stripe.com/v1/payment_intents', {
      method: 'POST',
      headers: { authorization: `Bearer ${stripeKey}`, 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        amount: '1200', currency: 'usd', payment_method: 'pm_card_visa', confirm: 'true',
        'payment_method_types[0]': 'card', 'metadata[order_id]': orderId,
        'metadata[item]': 'Tempo Notebook', 'metadata[quantity]': '1',
      }),
      signal: AbortSignal.timeout(30000),
    });
    const intent = await card.json() as { id?: string; status?: string };
    if (!card.ok || intent.status !== 'succeeded' || !intent.id?.startsWith('pi_')) {
      throw new Error(`Stripe card purchase failed: ${card.status}`);
    }
    appendFileSync(`${dir}/card-orders.jsonl`, JSON.stringify({ orderId, paymentIntentId: intent.id }) + '\n');
    return response.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify({
      orderId, item: 'Tempo Notebook', quantity: 1, amount: '12.00', currency: 'USD',
    }));
  } catch (error) {
    console.error(error);
    return response.writeHead(502).end('Upstream card purchase unavailable');
  }
}).listen(3001, '127.0.0.1');

http.createServer(async (request, response) => {
  const path = new URL(request.url || '/', 'http://merchant:3000').pathname;
  if (path === '/health') return response.writeHead(200).end('ok');
  if (path === '/' && request.method === 'GET') return response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(page);
  if (path === '/buy' && request.method === 'GET') {
    try {
      const result = await mppx.evm.charge({ amount: '12', description: 'Tempo Notebook' })(ServerRequest.fromNodeListener(request, response));
      if (result.status === 402) {
        const headers = new Headers(result.challenge.headers);
        headers.delete('www-authenticate');
        return NodeListener.sendResponse(response, new Response(await result.challenge.text(), { status: 402, headers }));
      }
      const upstream = await fetch('http://127.0.0.1:3001/deliver', { signal: AbortSignal.timeout(35000) });
      if (!upstream.ok) throw new Error(`Upstream card purchase failed: ${upstream.status}`);
      const order = await upstream.json() as { orderId: string; item: string; quantity: number; amount: string; currency: string };
      const paid = result.withReceipt(Response.json(order));
      appendFileSync(`${dir}/deliveries.jsonl`, JSON.stringify({
        ...order,
        receipt: paid.headers.get('payment-receipt'),
        paymentResponse: paid.headers.get('payment-response'),
      }) + '\n');
      return NodeListener.sendResponse(response, paid);
    } catch (error) {
      console.error(error);
      return response.writeHead(502).end('Checkout temporarily unavailable');
    }
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
