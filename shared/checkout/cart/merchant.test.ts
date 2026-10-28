import { test } from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const source = readFileSync(new URL('./merchant.js', import.meta.url), 'utf8');
const expected = JSON.parse(readFileSync(new URL('./order.json', import.meta.url), 'utf8'));
const address = JSON.parse(readFileSync(new URL('../shipping/address.json', import.meta.url), 'utf8'));

test('cart store prices the requested cart and records canonical immutable orders', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'checkout-cart-'));
  const module = join(directory, 'shipping.js');
  writeFileSync(join(directory, 'package.json'), '{"type":"module"}');
  writeFileSync(module, source.replace("'/var/log/checkout'", JSON.stringify(directory)));
  const { createShipping, shippingOrders } = await import(pathToFileURL(module).href);
  const shipping = createShipping('/buy');
  const server = http.createServer(async (request, response) => {
    if (await shipping.handle(request, response)) return;
    const order = shipping.get(request);
    response.writeHead(order ? 200 : 400, { 'content-type': 'application/json' }).end(JSON.stringify(order || { error: 'missing order' }));
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${(server.address() as any).port}`;
  const post = (body: unknown) => fetch(base + '/shipping', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
  try {
    const page = await (await fetch(base)).text();
    assert.match(page, /<form method="post" action="\/shipping">/);
    assert.match(page, /<option value="a4" selected>/);
    assert.match(page, /<option value="lined" selected>/);
    assert.match(page, /name="notebook_quantity" type="number" min="0" max="10" value="1"/);
    assert.match(page, /value="express" checked/);
    for (const field of Object.keys(address)) assert.ok(page.includes(`name="${field}"`));
    assert.ok(!page.includes(address.line1));

    const catalog = await (await fetch(base + '/catalog')).json();
    assert.equal(catalog.products.length, 8);
    assert.deepEqual(catalog.shippingOptions.map((option: any) => [option.id, option.price]), [['express', '15.00'], ['standard', '5.00']]);

    // Item order in the request does not change the recorded order.
    const created = await post({ items: [...expected.lines].reverse(), shippingOption: 'standard', shipping: address });
    assert.equal(created.status, 201);
    const body = await created.json();
    assert.equal(body.total, '33.00');
    const order = await (await fetch(body.paymentUrl.replace('http://merchant:3000', base))).json();
    assert.equal(order.total, expected.total);
    assert.equal(order.description, expected.description);
    assert.equal(order.shippingOption, expected.shippingOption);
    assert.deepEqual(order.lines.map(({ sku, quantity }: any) => ({ sku, quantity })), expected.lines);
    assert.deepEqual(order.shipping, address);

    const express = await (await post({ items: expected.lines, shippingOption: 'express', shipping: address })).json();
    assert.equal(express.total, '43.00');

    const form = await fetch(base + '/shipping', {
      method: 'POST', redirect: 'manual', headers: { 'content-type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ notebook_size: 'a5', notebook_ruling: 'dotted', notebook_quantity: '2', pen_quantity: '1', stickers_quantity: '0', shippingOption: 'standard', ...address }),
    });
    assert.equal(form.status, 303);
    const formOrder = await (await fetch(form.headers.get('location')!.replace('http://merchant:3000', base))).json();
    assert.equal(formOrder.description, expected.description);
    assert.equal(formOrder.total, expected.total);
    assert.equal(formOrder.source, 'form');

    for (const invalid of [
      { items: [], shippingOption: 'standard', shipping: address },
      { items: [{ sku: 'notebook-a5-grid', quantity: 2 }], shippingOption: 'standard', shipping: address },
      { items: [{ sku: 'pen', quantity: 1 }, { sku: 'pen', quantity: 1 }], shippingOption: 'standard', shipping: address },
      { items: [{ sku: 'pen', quantity: 0 }], shippingOption: 'standard', shipping: address },
      { items: [{ sku: 'pen', quantity: 1.5 }], shippingOption: 'standard', shipping: address },
      { items: [{ sku: 'pen', quantity: 1 }], shipping: address },
      { items: [{ sku: 'pen', quantity: 1 }], shippingOption: 'overnight', shipping: address },
      { items: [{ sku: 'pen', quantity: 1 }], shippingOption: 'standard', shipping: { ...address, country: 'United States' } },
    ]) assert.equal((await post(invalid)).status, 400, JSON.stringify(invalid));
    assert.equal(shippingOrders().length, 3);
  } finally {
    server.close();
    rmSync(directory, { recursive: true, force: true });
  }
});
