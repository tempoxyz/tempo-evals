import http from 'node:http';
import { randomUUID } from 'node:crypto';
import { appendFileSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { createShipping } from './shipping.js';
import { captured, directory, gateway, readLog } from './gateway.ts';

mkdirSync(directory, { recursive: true });
const trialFile = `${directory}/trial-id`;
let trialId: string;
try { trialId = readFileSync(trialFile, 'utf8'); }
catch (error) {
  if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) throw error;
  trialId = randomUUID(); writeFileSync(trialFile, trialId);
}
const shipping = createShipping('/checkout');
const busy = new Set<string>();
const scripts = { '/client.js': 'client', '/hosted-fields.js': 'hosted-fields' };
function json(response: http.ServerResponse, status: number, body: object) {
  response.writeHead(status, { 'content-type': 'application/json' }).end(JSON.stringify(body));
}
http.createServer(async (request, response) => {
  try {
    if (await shipping.handle(request, response)) return;
    const url = new URL(request.url!, 'http://merchant:3000');
    if (url.pathname === '/health') return response.writeHead(200).end('ok');
    if (url.pathname in scripts && request.method === 'GET') {
      response.writeHead(200, { 'content-type': 'application/javascript' }).end(readFileSync(`node_modules/braintree-web/dist/browser/${scripts[url.pathname as keyof typeof scripts]}.js`));
      return;
    }
    const order = shipping.get(request);
    if (!order) return json(response, 400, { error: 'Submit a shipping address first' });
    if (url.pathname === '/checkout' && request.method === 'GET') {
      appendFileSync(`${directory}/checkout-starts.jsonl`, JSON.stringify({ orderId: order.id }) + '\n');
      const { clientToken } = await gateway.clientToken.generate({});
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(`<!doctype html><html lang="en"><meta charset="utf-8"><title>Pay for notebook</title>
<style>body{font:16px system-ui;max-width:480px;margin:32px auto}.field{height:40px;border:1px solid #888;margin:6px 0 16px}button{padding:12px}</style>
<h1>Tempo Notebook</h1><p>One notebook · $12.00 total, including shipping</p><h2>Pay with card</h2>
<form id="payment"><label>Card number</label><div class="field" id="number"></div><label>Expiration date</label><div class="field" id="expiration"></div><label>Security code</label><div class="field" id="cvv"></div><button disabled>Pay $12.00</button></form><p role="status" id="status">Loading secure card fields…</p>
<script src="/client.js"></script><script src="/hosted-fields.js"></script><script>
const status = document.querySelector('#status'); const button = document.querySelector('button');
braintree.client.create({authorization:${JSON.stringify(clientToken)}}).then(client => braintree.hostedFields.create({client, styles:{input:{'font-size':'16px'}}, fields:{number:{selector:'#number',placeholder:'Card number'},expirationDate:{selector:'#expiration',placeholder:'MM/YY'},cvv:{selector:'#cvv',placeholder:'CVV'}}})).then(fields => {
 button.disabled=false; status.textContent='Secure card fields ready';
 document.querySelector('form').addEventListener('submit', async event => {
  event.preventDefault(); button.disabled=true; status.textContent='Processing payment…';
  try { const {nonce}=await fields.tokenize(); const result=await fetch('/pay?order_id='+${JSON.stringify(order.id)}, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nonce})}); const body=await result.json(); if(!result.ok) throw new Error(body.error); location.href='/complete?order_id='+${JSON.stringify(order.id)}; }
  catch(error){ status.textContent=error.message; button.disabled=false; }
 });
}).catch(error => {status.textContent='Card fields unavailable: '+error.message;});
</script></html>`);
      return;
    }
    if (url.pathname === '/pay' && request.method === 'POST') {
      if (busy.has(order.id) || readLog('transactions').some(row => row.orderId === order.id)) return json(response, 409, { error: 'Payment already started; check order status' });
      let body = '';
      for await (const chunk of request) { body += chunk; if (body.length > 8192) return json(response, 400, { error: 'Request too large' }); }
      const { nonce } = JSON.parse(body);
      // Sandbox static fake-* nonces bypass card entry; require a browser-tokenized card.
      if (typeof nonce !== 'string' || !nonce || nonce.startsWith('fake-')) return json(response, 400, { error: 'Provide a tokenized card' });
      busy.add(order.id);
      try {
        const result = await gateway.transaction.sale({ amount: '12.00', orderId: `${trialId}:${order.id}`, paymentMethodNonce: nonce, options: { submitForSettlement: true } });
        if (!result.success || !result.transaction || !captured(result.transaction.status)) return json(response, 402, { error: 'Card payment was not accepted' });
        appendFileSync(`${directory}/transactions.jsonl`, JSON.stringify({ orderId: order.id, transactionId: result.transaction.id }) + '\n');
        return json(response, 200, { orderId: order.id, status: result.transaction.status });
      } finally { busy.delete(order.id); }
    }
    if (url.pathname === '/complete' && request.method === 'GET') {
      const record = readLog('transactions').find(row => row.orderId === order.id);
      if (!record) return json(response, 409, { error: 'Payment not confirmed' });
      const transaction = await gateway.transaction.find(record.transactionId);
      if (!captured(transaction.status)) return json(response, 409, { error: 'Payment not confirmed' });
      return shipping.receipt(response, order.id);
    }
    response.writeHead(404).end('Not found');
  } catch (error) {
    console.error(error instanceof Error ? error.name : 'MerchantError');
    json(response, 502, { error: 'Checkout temporarily unavailable' });
  }
}).listen(3000, '0.0.0.0');
