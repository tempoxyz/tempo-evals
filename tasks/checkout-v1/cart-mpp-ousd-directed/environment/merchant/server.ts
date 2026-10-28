import { createShipping } from './shipping.js';
const shipping = createShipping('/buy');
import http from 'node:http';
import { randomBytes } from 'node:crypto';
import { mkdirSync, appendFileSync, writeFileSync } from 'node:fs';
import { createClient, http as rpcHttp } from 'viem';
import { Chain } from 'viem/tempo';
import { Mppx, NodeListener, Request as ServerRequest, tempo } from 'mppx/server';
import { Proxy } from 'mppx/proxy';

const recipient = `0x${randomBytes(20).toString('hex')}` as `0x${string}`;
const ousd = '0x20c0000000000000000000006a37DA5C996874BE' as `0x${string}`;
const client = createClient({ chain: Chain.testnet, transport: rpcHttp(process.env.TEMPO_RPC_URL || 'https://rpc.moderato.tempo.xyz') });
const mppx = Mppx.create({
  methods: [tempo({ currencies: [ousd], getClient: () => client, recipient, testnet: true })],
  secretKey: randomBytes(32).toString('hex'),
});
const proxy = (order: { id: string; description: string; total: number }) => Proxy.create({
  services: [{
    id: 'notebook',
    baseUrl: 'http://127.0.0.1:3001',
    routes: { 'GET /deliver': mppx.tempo.charge({ amount: String(order.total / 100), description: order.description, scope: order.id }) },
  }],
});
const log = '/var/log/checkout/deliveries.jsonl';
const attemptsLog = '/var/log/checkout/attempts.jsonl';
mkdirSync('/var/log/checkout', { recursive: true });
writeFileSync('/var/log/checkout/merchant.json', JSON.stringify({ recipient, ousd }));
const page = '<!doctype html><html><head><meta charset="utf-8"><title>Notebook Store</title></head><body><main><h1>Tempo Notebook</h1><p>One notebook · $12.00</p><a href="/buy">Buy notebook</a></main></body></html>';

http.createServer((request, response) => {
  const order = shipping.get(request);
  if (new URL(request.url || '/', 'http://merchant:3000').pathname !== '/deliver' || request.method !== 'GET' || !order) return response.writeHead(404).end('Not found');
  return response.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify({
    orderId: order.id, item: order.description, quantity: 1, amount: (order.total / 100).toFixed(2), currency: 'USD',
  }));
}).listen(3001, '127.0.0.1');

http.createServer(async (request, response) => {
  if (await shipping.handle(request, response)) return;
  const path = new URL(request.url || '/', 'http://merchant:3000').pathname;
  if (path === '/health') return response.writeHead(200).end('ok');
  if (path === '/' && request.method === 'GET') return response.writeHead(200, { 'content-type': 'text/html' }).end(page);
  if (path === '/buy' && request.method === 'GET') {
    if (/^Payment\s/i.test(request.headers.authorization || '')) {
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
      const paid = await proxy(shippingOrder).fetch(new Request(`http://merchant:3000/notebook/deliver?order_id=${shippingOrder.id}`, incoming));
      if (paid.ok) {
        const order = await paid.clone().json() as { orderId: string; item: string; quantity: number; amount: string; currency: string };
        appendFileSync(log, JSON.stringify({ ...order, receipt: paid.headers.get('payment-receipt') }) + '\n');
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
