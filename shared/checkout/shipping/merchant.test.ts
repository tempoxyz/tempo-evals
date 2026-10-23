import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
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
    const mixedCase = await fetch(base + '/shipping', { method: 'POST', headers: { 'content-type': 'Application/JSON ; charset=utf-8' }, body: JSON.stringify({ shipping: address }) });
    assert.equal(mixedCase.status, 201);
    const missingHeader = await fetch(base + '/shipping', { method: 'POST', body: JSON.stringify({ shipping: address }) });
    assert.equal(missingHeader.status, 400);
    assert.match((await missingHeader.json()).error, /Content-Type: application\/json/);
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
    assert.deepEqual(shippingOrders().find((o: any) => o.id === a.orderId).shipping, address);
  } finally {
    await new Promise<void>(resolve => server.close(() => resolve()));
    rmSync(directory, { recursive: true, force: true });
  }
});

test('PayPal inspection and repeated returns keep one captured order', async t => {
  const directory = mkdtempSync(join(tmpdir(), 'checkout-paypal-'));
  writeFileSync(join(directory, 'package.json'), '{"type":"module"}');
  writeFileSync(join(directory, 'shipping.js'), source.replace("'/var/log/checkout'", JSON.stringify(directory)));
  const merchant = readFileSync(new URL('../../../tasks/checkout-v1/paypal-discover/environment/merchant/server.js', import.meta.url), 'utf8');
  writeFileSync(join(directory, 'server.js'), merchant.replaceAll('/var/log/checkout', directory)
    .replace('http.createServer(', 'export const server = http.createServer(')
    .replace(".listen(3000, '0.0.0.0')", ".listen(0, '127.0.0.1')"));
  const originalFetch = globalThis.fetch;
  const keys = ['PAYPAL_SANDBOX_CLIENT_ID', 'PAYPAL_SANDBOX_CLIENT_SECRET'];
  const originalKeys = keys.map(key => process.env[key]);
  for (const key of keys) process.env[key] = 'sandbox-fixture';
  const orders = new Map<string, any>();
  let captures = 0;
  t.mock.method(globalThis, 'fetch', async (url: any, init: any) => {
    if (!String(url).startsWith('https://api-m.sandbox.paypal.com/')) return originalFetch(url, init);
    const path = new URL(String(url)).pathname;
    if (path === '/v1/oauth2/token') return new Response('{"access_token":"fixture"}');
    if (path === '/v2/checkout/orders' && init.method === 'POST') {
      const id = `PAYPAL${orders.size + 1}`;
      const order = { ...JSON.parse(init.body), id, status: 'CREATED', links: [{ rel: 'payer-action', href: `https://www.sandbox.paypal.com/checkoutnow?token=${id}` }] };
      orders.set(id, order);
      await new Promise(resolve => setTimeout(resolve, 15));
      return new Response(JSON.stringify(order));
    }
    const id = path.split('/')[4];
    const order = orders.get(id);
    if (!order) return new Response('{}', { status: 404 });
    if (path.endsWith('/capture')) {
      if (order.status !== 'APPROVED') return new Response('{}', { status: 422 });
      order.status = 'COMPLETED';
      order.purchase_units[0].payments = { captures: [{ status: 'COMPLETED' }] };
      captures++;
      // Reconcile a capture that completed despite a failed HTTP response.
      return new Response('{}', { status: 500 });
    }
    return new Response(JSON.stringify(order));
  });
  let server: http.Server | undefined;
  try {
    ({ server } = await import(pathToFileURL(join(directory, 'server.js')).href));
    if (!server!.address()) await new Promise(resolve => server!.once('listening', resolve));
    const base = `http://127.0.0.1:${(server!.address() as any).port}`;
    const get = (path: string) => originalFetch(base + path, { redirect: 'manual' });
    const address = JSON.parse(readFileSync(new URL('./address.json', import.meta.url), 'utf8'));
    const create = async () => (await originalFetch(base + '/shipping', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ shipping: address }) })).json();
    const order = await create();
    const path = '/checkout?order_id=' + order.orderId;
    const checkouts = await Promise.all([get(path), get(path)]);
    for (const checkout of checkouts) {
      assert.equal(checkout.status, 303);
      assert.match(checkout.headers.get('location')!, /token=PAYPAL1$/);
    }
    assert.equal(orders.size, 1);
    assert.match((await get(path)).headers.get('location')!, /token=PAYPAL1$/);
    assert.equal((await get('/complete?order_id=' + order.orderId)).status, 409);
    orders.get('PAYPAL1').status = 'APPROVED';
    assert.equal((await get(path)).headers.get('location'), '/return?token=PAYPAL1');
    const returned = await get('/return?token=PAYPAL1');
    assert.equal(returned.status, 303);
    const receipt = await get(returned.headers.get('location')!);
    assert.equal(receipt.status, 200);
    assert.match(await receipt.text(), /Apt 4B/);
    assert.equal((await get('/return?token=PAYPAL1')).status, 303);
    assert.equal(captures, 1);
    assert.equal((await get(path)).status, 200);
    const second = await create();
    assert.match((await get('/checkout?order_id=' + second.orderId)).headers.get('location')!, /token=PAYPAL2$/);
    assert.equal(orders.size, 2);
    assert.equal(readFileSync(join(directory, 'orders.jsonl'), 'utf8').trim().split('\n').length, 2);
    assert.equal(readFileSync(join(directory, 'checkout-starts.jsonl'), 'utf8').trim().split('\n').length, 6);
  } finally {
    if (server) await new Promise<void>(resolve => server!.close(() => resolve()));
    for (const [index, name] of keys.entries()) {
      if (originalKeys[index] === undefined) delete process.env[name];
      else process.env[name] = originalKeys[index];
    }
    rmSync(directory, { recursive: true, force: true });
  }
});

test('Link inspection, refresh and concurrent requests reuse one intent per order', async t => {
  const directory = mkdtempSync(join(tmpdir(), 'checkout-link-'));
  writeFileSync(join(directory, 'package.json'), '{"type":"module"}');
  writeFileSync(join(directory, 'shipping.js'), source.replace("'/var/log/checkout'", JSON.stringify(directory)));
  const merchant = readFileSync(new URL('../../../tasks/checkout-v1/stripe-link-discover/environment/merchant/server.js', import.meta.url), 'utf8');
  writeFileSync(join(directory, 'server.js'), merchant.replaceAll('/var/log/checkout', directory)
    .replace('http.createServer(', 'export const server = http.createServer(')
    .replace(".listen(3000, '0.0.0.0')", ".listen(0, '127.0.0.1')"));
  const originalFetch = globalThis.fetch;
  const originalKeys = [process.env.STRIPE_TEST_SECRET_KEY, process.env.STRIPE_TEST_PUBLISHABLE_KEY];
  process.env.STRIPE_TEST_SECRET_KEY = 'sk_test_fixture';
  process.env.STRIPE_TEST_PUBLISHABLE_KEY = 'pk_test_fixture';
  const byKey = new Map<string, any>();
  const byId = new Map<string, any>();
  const activeKeys = new Set<string>();
  let conflicts = 0;
  let failNextCreate = false;
  const failedKeys = new Set<string>();
  t.mock.method(globalThis, 'fetch', async (url: any, init: any) => {
    if (!String(url).startsWith('https://api.stripe.com/')) return originalFetch(url, init);
    let intent;
    if (init.method === 'POST') {
      const key = new Headers(init.headers).get('idempotency-key');
      assert.ok(key);
      if (failNextCreate || failedKeys.has(key!)) {
        failNextCreate = false;
        failedKeys.add(key!);
        return new Response('{"error":"temporary_error"}', { status: 500 });
      }
      if (activeKeys.has(key!)) {
        conflicts++;
        return new Response('{"error":"idempotency_key_in_use"}', { status: 409 });
      }
      activeKeys.add(key!);
      intent = byKey.get(key!);
      if (!intent) {
        const id = `pi_fixture${byId.size + 1}`;
        intent = { id, client_secret: `${id}_secret_fixture`, livemode: false, status: 'requires_payment_method' };
        byKey.set(key!, intent);
        byId.set(id, intent);
      }
      await new Promise(resolve => setTimeout(resolve, 15));
      activeKeys.delete(key!);
    } else intent = byId.get(String(url).split('/').at(-1));
    return new Response(JSON.stringify(intent), { status: intent ? 200 : 404 });
  });
  let server: http.Server | undefined;
  try {
    ({ server } = await import(pathToFileURL(join(directory, 'server.js')).href));
    if (!server!.address()) await new Promise(resolve => server!.once('listening', resolve));
    const base = `http://127.0.0.1:${(server!.address() as any).port}`;
    const address = JSON.parse(readFileSync(new URL('./address.json', import.meta.url), 'utf8'));
    const order = await (await originalFetch(base + '/shipping', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ shipping: address }) })).json();
    const checkout = base + '/checkout?order_id=' + order.orderId;
    const pages = await Promise.all([originalFetch(checkout), originalFetch(checkout)]);
    for (const page of pages) assert.match(await page.text(), /pi_fixture1_secret_fixture/);
    assert.equal(conflicts, 0);
    assert.equal(byId.size, 1);
    assert.equal(readFileSync(join(directory, 'intents.jsonl'), 'utf8').trim().split('\n').length, 1);
    assert.match(await (await originalFetch(checkout)).text(), /pi_fixture1_secret_fixture/);
    assert.equal((await originalFetch(base + '/complete?order_id=' + order.orderId)).status, 409);
    byId.get('pi_fixture1').status = 'succeeded';
    const complete = await originalFetch(base + '/complete?order_id=' + order.orderId);
    assert.equal(complete.status, 200);
    assert.match(await complete.text(), /Apt 4B/);
    assert.match(await (await originalFetch(checkout)).text(), /Payment confirmed/);
    assert.equal(byId.size, 1);
    const second = await (await originalFetch(base + '/shipping', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ shipping: address }) })).json();
    assert.match(await (await originalFetch(base + '/checkout?order_id=' + second.orderId)).text(), /pi_fixture2_secret_fixture/);
    assert.equal(byId.size, 2);
    assert.equal(readFileSync(join(directory, 'intents.jsonl'), 'utf8').trim().split('\n').length, 2);
    failNextCreate = true;
    const third = await (await originalFetch(base + '/shipping', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ shipping: address }) })).json();
    const retryUrl = base + '/checkout?order_id=' + third.orderId;
    assert.equal((await originalFetch(retryUrl)).status, 502);
    assert.match(await (await originalFetch(retryUrl)).text(), /pi_fixture3_secret_fixture/);
    assert.equal(failedKeys.size, 1);
    assert.equal(readFileSync(join(directory, 'checkout-starts.jsonl'), 'utf8').trim().split('\n').length, 7);
    assert.equal((await originalFetch(base + '/complete?order_id=unknown')).status, 404);
  } finally {
    if (server) await new Promise<void>(resolve => server!.close(() => resolve()));
    for (const [index, name] of ['STRIPE_TEST_SECRET_KEY', 'STRIPE_TEST_PUBLISHABLE_KEY'].entries()) {
      if (originalKeys[index] === undefined) delete process.env[name];
      else process.env[name] = originalKeys[index];
    }
    rmSync(directory, { recursive: true, force: true });
  }
});
