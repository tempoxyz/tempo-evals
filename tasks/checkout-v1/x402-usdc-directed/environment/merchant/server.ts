import { createShipping } from './shipping.js';
const shipping = createShipping('/buy', { price: '1.00' });
import http from 'node:http';
import { randomBytes } from 'node:crypto';
import { existsSync, mkdirSync, appendFileSync, readFileSync, writeFileSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';
import { privateKeyToAccount } from 'viem/accounts';
import { Mppx, NodeListener, Request as ServerRequest, evm } from 'mppx/server';
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
// Charge on the order's own payment URL, so the x402 challenge's resource is the
// URL the agent requested. The scope binds the payment to that shipping order.
const charge = (orderId: string) => mppx.evm.charge({ amount: '1', description: 'Tempo Notebook', scope: orderId });
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
      const result = await charge(shippingOrder.id)(ServerRequest.fromNodeListener(request, response));
      if (result.status === 402) {
        // Advertise only x402: drop the native MPP challenge and its MPP-specific
        // problem body, and return the x402 payment requirements instead.
        const headers = new Headers(result.challenge.headers);
        headers.delete('www-authenticate');
        headers.set('content-type', 'application/json');
        const required = headers.get('payment-required');
        const body = required ? Buffer.from(required, 'base64').toString('utf8') : '{}';
        return NodeListener.sendResponse(response, new Response(body, { status: 402, headers }));
      }
      const order = { orderId: shippingOrder.id, item: 'Tempo Notebook', quantity: 1, amount: '1.00', currency: 'USD' };
      const paid = result.withReceipt(Response.json(order));
      appendFileSync(log, JSON.stringify({ ...order, receipt: paid.headers.get('payment-receipt'), paymentResponse: paid.headers.get('payment-response') }) + '\n');
      return NodeListener.sendResponse(response, paid);
    } catch (error) {
      console.error(error);
      response.writeHead(502).end('Checkout temporarily unavailable');
      return;
    }
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
