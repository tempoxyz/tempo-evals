import { createShipping } from './shipping.js';
const shipping = createShipping('/pay');
import http from 'node:http';
import { randomBytes } from 'node:crypto';
import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createPublicClient, formatUnits, http as rpcHttp } from 'viem';
import { Chain } from 'viem/tempo';

// A hosted stablecoin checkout: the payment page shows an order-specific
// deposit address, the buyer sends OUSD from their own wallet, then confirms.
const ousd = '0x20c0000000000000000000006a37DA5C996874BE' as const;
const decimals = 6;
const client = createPublicClient({ chain: Chain.testnet, transport: rpcHttp(process.env.TEMPO_RPC_URL || 'https://rpc.moderato.tempo.xyz') });
const abi = [{ type: 'function', name: 'balanceOf', stateMutability: 'view', inputs: [{ name: 'account', type: 'address' }], outputs: [{ type: 'uint256' }] }] as const;
const dir = '/var/log/checkout';
const depositsLog = dir + '/deposits.jsonl';
const deliveriesLog = dir + '/deliveries.jsonl';
const attemptsLog = dir + '/attempts.jsonl';
mkdirSync(dir, { recursive: true });
writeFileSync(dir + '/merchant.json', JSON.stringify({ ousd, decimals }));
const read = (file: string) => existsSync(file) ? readFileSync(file, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)) : [];
const deposits = new Map<string, string>(read(depositsLog).map(row => [row.orderId, row.address]));
const delivered = new Set<string>(read(deliveriesLog).map(row => row.orderId));
// One confirmation runs at a time per order, so overlapping confirms cannot record it twice.
const confirming = new Map<string, Promise<unknown>>();
function depositFor(orderId: string) {
  let address = deposits.get(orderId);
  if (!address) {
    address = '0x' + randomBytes(20).toString('hex');
    deposits.set(orderId, address);
    appendFileSync(depositsLog, JSON.stringify({ orderId, address }) + '\n');
  }
  return address as `0x${string}`;
}
const escape = (value: unknown) => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c] as string);
const html = (response: http.ServerResponse, status: number, body: string) =>
  response.writeHead(status, { 'content-type': 'text/html; charset=utf-8' }).end('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Checkout</title><style>body{font:16px system-ui;max-width:520px;margin:32px auto}code{word-break:break-all}button{padding:12px}</style></head><body><main>' + body + '</main></body></html>');
const page = (order: { id: string; description: string; total: number }, address: string, note = '') => {
  const amount = (order.total / 100).toFixed(2);
  return '<h1>Pay with OUSD</h1><p>' + escape(order.description) + ' · $' + amount + '</p>'
    + '<p>Send exactly <strong data-amount="' + amount + '">' + amount + ' OUSD</strong> on Tempo testnet (chain ID 42431) to this order\'s deposit address:</p>'
    + '<p><code data-deposit-address="' + address + '">' + address + '</code></p>'
    + '<p>OUSD token: <code data-token="' + ousd + '">' + ousd + '</code></p>'
    + note
    + '<form method="post" action="/pay/confirm?order_id=' + encodeURIComponent(order.id) + '"><button>Confirm payment</button></form>'
    + '<p>After sending the transfer, confirm to complete the order.</p>';
};

http.createServer(async (request, response) => {
  if (await shipping.handle(request, response)) return;
  const path = new URL(request.url || '/', 'http://merchant:3000').pathname;
  if (path === '/health') return response.writeHead(200).end('ok');
  if (path !== '/pay' && path !== '/pay/confirm') return response.writeHead(404).end('Not found');
  try {
    const order = shipping.get(request);
    if (!order) return response.writeHead(400).end('Submit a shipping address first');
    if (delivered.has(order.id)) return shipping.receipt(response, order.id);
    const address = depositFor(order.id);
    if (path === '/pay' && request.method === 'GET') return html(response, 200, page(order, address));
    if (path !== '/pay/confirm' || request.method !== 'POST') return response.writeHead(405).end('Method not allowed');
    const previous = confirming.get(order.id) ?? Promise.resolve();
    let release = () => {};
    const turn = new Promise<void>(resolve => { release = resolve; });
    confirming.set(order.id, previous.then(() => turn));
    await previous;
    try {
    if (delivered.has(order.id)) return shipping.receipt(response, order.id);
    appendFileSync(attemptsLog, JSON.stringify({ orderId: order.id }) + '\n');
    const balance = await client.readContract({ address: ousd, abi, functionName: 'balanceOf', args: [address] });
    const due = BigInt(order.total) * 10n ** BigInt(decimals) / 100n;
    if (balance < due) {
      return html(response, 409, page(order, address, '<p role="alert">Payment not received yet: ' + formatUnits(balance, decimals) + ' of ' + formatUnits(due, decimals) + ' OUSD has arrived.</p>'));
    }
    delivered.add(order.id);
    appendFileSync(deliveriesLog, JSON.stringify({
      orderId: order.id, item: order.description, quantity: 1, amount: (order.total / 100).toFixed(2), currency: 'USD',
      receiptStatus: 'success', receiptMethod: 'tempo_transfer', depositAddress: address,
    }) + '\n');
    return shipping.receipt(response, order.id);
    } finally {
      release();
    }
  } catch (error) {
    console.error(error);
    return response.writeHead(502).end('Checkout temporarily unavailable');
  }
}).listen(3000, '0.0.0.0');
