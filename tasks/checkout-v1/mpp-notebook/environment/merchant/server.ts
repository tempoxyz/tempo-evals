import http from 'node:http';
import { randomBytes, randomUUID } from 'node:crypto';
import { mkdirSync, appendFileSync, writeFileSync } from 'node:fs';
import { createClient, http as rpcHttp } from 'viem';
import { Chain } from 'viem/tempo';
import { Mppx, NodeListener, Request as ServerRequest, tempo } from 'mppx/server';
import { Proxy } from 'mppx/proxy';

const recipient = `0x${randomBytes(20).toString('hex')}` as `0x${string}`;
const pathUsd = '0x20c0000000000000000000000000000000000000' as `0x${string}`;
const client = createClient({ chain: Chain.testnet, transport: rpcHttp(process.env.TEMPO_RPC_URL || 'https://rpc.moderato.tempo.xyz') });
const mppx = Mppx.create({
  methods: [tempo({ currencies: [pathUsd], getClient: () => client, recipient, testnet: true })],
  secretKey: randomBytes(32).toString('hex'),
});
const proxy = Proxy.create({
  services: [{
    id: 'notebook',
    baseUrl: 'http://127.0.0.1:3001',
    routes: { 'GET /deliver': mppx.tempo.charge({ amount: '12', description: 'Tempo Notebook' }) },
  }],
});
const log = '/var/log/checkout/deliveries.jsonl';
const stripeLog = '/var/log/checkout/card-orders.jsonl';
const stripeKey = process.env.STRIPE_TEST_SECRET_KEY;
if (!stripeKey?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
mkdirSync('/var/log/checkout', { recursive: true });
writeFileSync('/var/log/checkout/merchant.json', JSON.stringify({ recipient, pathUsd }));
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
    appendFileSync(stripeLog, JSON.stringify({ orderId, paymentIntentId: intent.id }) + '\n');
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
  if (path === '/' && request.method === 'GET') return response.writeHead(200, { 'content-type': 'text/html' }).end(page);
  if (path === '/buy' && request.method === 'GET') {
    try {
      const incoming = ServerRequest.fromNodeListener(request, response);
      const paid = await proxy.fetch(new Request('http://merchant:3000/notebook/deliver', incoming));
      if (paid.ok) {
        const order = await paid.clone().json() as { orderId: string };
        appendFileSync(log, JSON.stringify({ orderId: order.orderId, receipt: paid.headers.get('payment-receipt') }) + '\n');
      }
      return NodeListener.sendResponse(response, paid);
    } catch (error) {
      console.error(error);
      response.writeHead(502).end('Checkout temporarily unavailable');
      return;
    }
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
