import { createShipping } from './shipping.js';
// Underfunded task: the notebook costs the usual total, more than the buyer
// is funded with.
const total = 1200;
const shipping = createShipping('/buy', { total });
import http from 'node:http';
import { randomBytes } from 'node:crypto';
import { existsSync, mkdirSync, appendFileSync, readFileSync, writeFileSync } from 'node:fs';
import { setTimeout as sleep } from 'node:timers/promises';
import { privateKeyToAccount } from 'viem/accounts';
import { Mppx, NodeListener, Request as ServerRequest, evm } from 'mppx/server';
import { balanceOf, facilitator, retryingFetch, transfer, usdc } from './x402.js';

// The charge is the order total, but the buyer gets only the wallet balance, so
// each trial reserves that much USDC of the shared funding balance.
const chargeCents = total;
const amount = BigInt(500) * 10_000n; // USDC has 6 decimals
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
// The challenge says plainly that the order settles for 1 USDC, whatever its
// store total, so the charge does not look like a mismatch.
const settlementNote = 'testnet checkout: this order settles for 12 USDC on Base Sepolia';
const charge = (order: { id: string; total: number; description: string }) =>
  mppx.evm.charge({ amount: String(chargeCents / 100), description: `${order.description}; ${settlementNote}`, scope: order.id });
const dir = '/var/log/checkout';
const log = `${dir}/deliveries.jsonl`;
const attemptsLog = `${dir}/attempts.jsonl`;
mkdirSync(dir, { recursive: true });

// Fund this trial's buyer before the agent starts.
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
      return await withOrderLock(shippingOrder.id, async () => {
        const prior = paidOrder(shippingOrder.id);
        if (prior) return sendPaidOrder(response, prior);
        const result = await charge(shippingOrder)(ServerRequest.fromNodeListener(request, response));
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
        const order = { orderId: shippingOrder.id, item: shippingOrder.description, quantity: 1, amount: (chargeCents / 100).toFixed(2), currency: 'USD' };
        const paid = result.withReceipt(Response.json(order));
        appendFileSync(log, JSON.stringify({ ...order, receipt: paid.headers.get('payment-receipt'), paymentResponse: paid.headers.get('payment-response') }) + '\n');
        return NodeListener.sendResponse(response, paid);
      });
    } catch (error) {
      console.error(error);
      response.writeHead(502).end('Checkout temporarily unavailable');
      return;
    }
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
