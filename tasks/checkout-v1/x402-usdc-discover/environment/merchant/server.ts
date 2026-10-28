import { createShipping } from './shipping.js';
const shipping = createShipping('/buy', { price: '1.00' });
import http from 'node:http';
import { randomBytes } from 'node:crypto';
import { existsSync, mkdirSync, appendFileSync, readFileSync, writeFileSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';
import { privateKeyToAccount } from 'viem/accounts';
import { Mppx, NodeListener, Request as ServerRequest, evm } from 'mppx/server';
import { Proxy } from 'mppx/proxy';
import { balanceOf, facilitator, retryingFetch, transfer, usdc } from './x402.js';

const amount = 1_000_000n;
const fundingKey = process.env.X402_FUNDING_PRIVATE_KEY as `0x${string}`;
if (!/^0x[0-9a-fA-F]{64}$/.test(fundingKey || '')) throw new Error('X402_FUNDING_PRIVATE_KEY is required');
// Payments return to the funding wallet, so successful trials refill it.
const funding = privateKeyToAccount(fundingKey);
const recipient = funding.address;
const mppx = Mppx.create({
  methods: [evm.charge({ currency: evm.assets.baseSepolia.USDC, recipient, x402: { facilitator, fetch: retryingFetch } })],
  secretKey: randomBytes(32).toString('hex'),
});
const proxy = (orderId: string) => Proxy.create({
  services: [{
    id: 'notebook',
    baseUrl: 'http://127.0.0.1:3001',
    routes: { 'GET /deliver': mppx.evm.charge({ amount: '1', description: 'Tempo Notebook', scope: orderId }) },
  }],
});
const dir = '/var/log/checkout';
const log = `${dir}/deliveries.jsonl`;
const attemptsLog = `${dir}/attempts.jsonl`;
mkdirSync(dir, { recursive: true });

// Fund this trial's buyer with exactly the price before the agent starts.
const wallet = JSON.parse(readFileSync('/wallet/wallet.json', 'utf8'));
const buyer = wallet.baseSepolia.address as `0x${string}`;
if (!existsSync(`${dir}/funding.json`)) {
  const transaction = await transfer(funding, buyer, amount);
  for (let attempt = 0; (await balanceOf(buyer)) < amount; attempt++) {
    if (attempt >= 60) throw new Error('Base Sepolia buyer funding was not confirmed');
    await sleep(1_000);
  }
  writeFileSync(`${dir}/funding.json`, JSON.stringify({ buyer, amount: amount.toString(), transaction }));
}
writeFileSync(`${dir}/merchant.json`, JSON.stringify({ recipient, usdc, buyer }));
const page = '<!doctype html><html><head><meta charset="utf-8"><title>Notebook Store</title></head><body><main><h1>Tempo Notebook</h1><p>One notebook · $1.00</p><a href="/buy">Buy notebook</a></main></body></html>';

http.createServer((request, response) => {
  if (new URL(request.url || '/', 'http://merchant:3000').pathname !== '/deliver' || request.method !== 'GET') return response.writeHead(404).end('Not found');
  return response.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify({
    orderId: new URL(request.url || '/', 'http://merchant:3000').searchParams.get('order_id'), item: 'Tempo Notebook', quantity: 1, amount: '1.00', currency: 'USD',
  }));
}).listen(3001, '127.0.0.1');

http.createServer(async (request, response) => {
  if (await shipping.handle(request, response)) return;
  const path = new URL(request.url || '/', 'http://merchant:3000').pathname;
  if (path === '/health') return response.writeHead(200).end('ok');
  if (path === '/' && request.method === 'GET') return response.writeHead(200, { 'content-type': 'text/html' }).end(page);
  if (path === '/buy' && request.method === 'GET') {
    if (request.headers['payment-signature'] || request.headers['x-payment'] || /^Payment\s/i.test(request.headers.authorization || '')) {
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
      if (paid.status === 402) {
        // Advertise only x402, not the native MPP challenge for the same charge.
        const headers = new Headers(paid.headers);
        headers.delete('www-authenticate');
        return NodeListener.sendResponse(response, new Response(await paid.text(), { status: 402, headers }));
      }
      if (paid.ok) {
        const order = await paid.clone().json() as { orderId: string; item: string; quantity: number; amount: string; currency: string };
        appendFileSync(log, JSON.stringify({ ...order, receipt: paid.headers.get('payment-receipt'), paymentResponse: paid.headers.get('payment-response') }) + '\n');
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
