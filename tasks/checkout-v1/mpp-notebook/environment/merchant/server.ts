import http from 'node:http';
import { randomBytes, randomUUID } from 'node:crypto';
import { mkdirSync, appendFileSync, writeFileSync } from 'node:fs';
import { createClient, http as rpcHttp } from 'viem';
import { Chain } from 'viem/tempo';
import { Mppx, NodeListener, Request as ServerRequest, tempo } from 'mppx/server';

const recipient = `0x${randomBytes(20).toString('hex')}` as `0x${string}`;
const pathUsd = '0x20c0000000000000000000000000000000000000' as `0x${string}`;
const client = createClient({ chain: Chain.testnet, transport: rpcHttp(process.env.TEMPO_RPC_URL || 'https://rpc.moderato.tempo.xyz') });
const mppx = Mppx.create({
  methods: [tempo({ currencies: [pathUsd], getClient: () => client, recipient, testnet: true })],
  secretKey: randomBytes(32).toString('hex'),
});
const log = '/var/log/checkout/deliveries.jsonl';
mkdirSync('/var/log/checkout', { recursive: true });
writeFileSync('/var/log/checkout/merchant.json', JSON.stringify({ recipient, pathUsd }));
const page = '<!doctype html><html><head><meta charset="utf-8"><title>Notebook Store</title></head><body><main><h1>Tempo Notebook</h1><p>One notebook · $12.00</p><a href="/buy">Buy notebook</a></main></body></html>';

http.createServer(async (request, response) => {
  const path = new URL(request.url || '/', 'http://merchant:3000').pathname;
  if (path === '/health') return response.writeHead(200).end('ok');
  if (path === '/' && request.method === 'GET') return response.writeHead(200, { 'content-type': 'text/html' }).end(page);
  if (path === '/buy' && request.method === 'GET') {
    try {
      const result = await mppx.tempo.charge({ amount: '12', description: 'Tempo Notebook' })(ServerRequest.fromNodeListener(request, response));
      if (result.status === 402) return NodeListener.sendResponse(response, result.challenge);
      const orderId = randomUUID();
      const paid = result.withReceipt(Response.json({ orderId, item: 'Tempo Notebook', quantity: 1, amount: '12.00', currency: 'USD' }));
      appendFileSync(log, JSON.stringify({ orderId, receipt: paid.headers.get('payment-receipt') }) + '\n');
      return NodeListener.sendResponse(response, paid);
    } catch (error) {
      console.error(error);
      response.writeHead(502).end('Checkout temporarily unavailable');
      return;
    }
  }
  response.writeHead(404).end('Not found');
}).listen(3000, '0.0.0.0');
