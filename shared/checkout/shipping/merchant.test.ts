import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

// The merchant module lives in a sidecar at this absolute evidence path.
// Exercise it in Docker for runtime tests; this test verifies its public form
// contract without importing its production filesystem location.
const source = readFileSync(new URL('./merchant.js', import.meta.url), 'utf8');
test('shipping form and API preserve entered fields and bind immutable orders', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'checkout-shipping-'));
  const { writeFileSync } = await import('node:fs');
  const module = join(directory, 'shipping.js');
  writeFileSync(join(directory, 'package.json'), '{"type":"module"}');
  writeFileSync(module, source.replace("'/var/log/checkout'", JSON.stringify(directory)));
  const { createShipping, shippingOrders } = await import(pathToFileURL(module).href);
  const shipping = createShipping('/buy');
  const server = http.createServer(async (request, response) => {
    if (await shipping.handle(request, response)) return;
    if (request.method !== 'GET' || !request.url?.startsWith('/buy')) { response.writeHead(404).end(); return; }
    const order = shipping.get(request);
    response.writeHead(order ? 200 : 400, { 'content-type': 'application/json' }).end(JSON.stringify(order || { error: 'missing shipping' }));
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = (server.address() as any).port;
  const base = `http://127.0.0.1:${port}`;
  const address = JSON.parse(readFileSync(new URL('./address.json', import.meta.url), 'utf8'));
  try {
    const page = await (await fetch(base)).text();
    assert.match(page, /<form method="post" action="\/shipping">/);
    for (const field of Object.keys(address)) assert.ok(page.includes(`name="${field}"`));
    assert.ok(!page.includes(address.line1));
    assert.equal((await fetch(base + '/buy')).status, 400);
    const post = async (shipping: any) => fetch(base + '/shipping', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ shipping }) });
    assert.equal((await post({ name: 'Missing fields' })).status, 400);
    assert.equal((await post({ ...address, country: 'United States' })).status, 400);
    const first = await post(address);
    assert.equal(first.status, 201);
    const a = await first.json();
    assert.deepEqual(a.shipping, address);
    const form = await fetch(base + '/shipping', { method: 'POST', headers: { 'content-type': 'application/x-www-form-urlencoded' }, body: new URLSearchParams(address), redirect: 'manual' });
    assert.equal(form.status, 303);
    assert.match(form.headers.get('location')!, /order_id=/);
    // A syntactically valid wrong destination is accepted by the store and is
    // rejected by the independent verifier, not by a hardcoded merchant answer.
    const b = await (await post({ ...address, line2: 'Apt 999' })).json();
    assert.notEqual(a.orderId, b.orderId);
    const current = await (await fetch(base + '/buy?order_id=' + a.orderId)).json();
    assert.deepEqual(current.shipping, address);
    assert.equal((await fetch(base + '/shipping?order_id=' + a.orderId, { method: 'PUT' })).status, 404);
    assert.equal(shippingOrders().filter((o: any) => o.id === a.orderId).length, 1);
    assert.deepEqual(shippingOrders()[0].shipping, address);
  } finally {
    await new Promise<void>(resolve => server.close(() => resolve()));
    rmSync(directory, { recursive: true, force: true });
  }
});
