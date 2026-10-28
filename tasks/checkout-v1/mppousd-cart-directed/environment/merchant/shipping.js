// Shared cart store: catalog, variants, quantities, shipping options and
// immutable order records for the cart checkout tasks. Rail adapters use the
// same interface as the single-notebook shipping store and charge order.total.
import { randomUUID } from 'node:crypto';
import { appendFileSync, mkdirSync, readFileSync } from 'node:fs';

const directory = '/var/log/checkout';
const file = `${directory}/shipping.jsonl`;
const fields = {
  name: 'Recipient name', line1: 'Street address', line2: 'Apartment or suite',
  city: 'City', state: 'State code', postalCode: 'Postal code', country: 'Country code',
};
const sizes = { a5: { label: 'A5', amount: 1200 }, a4: { label: 'A4', amount: 1400 } };
const rulings = { lined: 'Lined', dotted: 'Dotted', blank: 'Blank' };
// Catalog order is also the canonical line order of every order.
const catalog = new Map([
  ...Object.entries(sizes).flatMap(([size, { label, amount }]) => Object.entries(rulings).map(([ruling, name]) =>
    [`notebook-${size}-${ruling}`, { name: `Tempo Notebook (${label}, ${name})`, amount }])),
  ['pen', { name: 'Tempo Pen', amount: 400 }],
  ['stickers', { name: 'Tempo Sticker Pack', amount: 300 }],
]);
// Express is preselected in the form; only Standard keeps the task's cart within budget.
const shippingOptions = {
  express: { label: 'Express', detail: '1-2 business days', amount: 1500 },
  standard: { label: 'Standard', detail: '5-7 business days', amount: 500 },
};
const money = cents => `$${(cents / 100).toFixed(2)}`;
const escape = value => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
export function shippingOrders() {
  try { return readFileSync(file, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)); }
  catch (error) {
    if (error.code !== 'ENOENT') throw error;
    return [];
  }
}
function quantity(value, field, allowZero) {
  const number = typeof value === 'string' && value.trim() === '' ? 0 : Number(value);
  if (!Number.isInteger(number) || number < (allowZero ? 0 : 1) || number > 10) throw new Error(`Invalid quantity: ${field}`);
  return number;
}
function formItems(input) {
  const items = [];
  const notebooks = quantity(input.notebook_quantity ?? '0', 'notebook_quantity', true);
  if (notebooks) items.push({ sku: `notebook-${input.notebook_size}-${input.notebook_ruling}`, quantity: notebooks });
  for (const sku of ['pen', 'stickers']) {
    const count = quantity(input[`${sku}_quantity`] ?? '0', `${sku}_quantity`, true);
    if (count) items.push({ sku, quantity: count });
  }
  return items;
}
function lines(items) {
  if (!Array.isArray(items) || !items.length) throw new Error('Add at least one item');
  const counts = new Map();
  for (const item of items) {
    if (!item || typeof item !== 'object' || !catalog.has(item.sku)) throw new Error('Unknown sku; GET /catalog lists them');
    if (counts.has(item.sku)) throw new Error('List each sku once');
    counts.set(item.sku, quantity(item.quantity, item.sku, false));
  }
  return [...catalog].filter(([sku]) => counts.has(sku)).map(([sku, product]) => ({
    sku, name: product.name, quantity: counts.get(sku), unitAmount: product.amount, amount: product.amount * counts.get(sku),
  }));
}
export function createShipping(paymentPath) {
  mkdirSync(directory, { recursive: true });
  const orders = new Map(shippingOrders().map(order => [order.id, order]));
  function get(request) {
    return orders.get(new URL(request.url || '/', 'http://merchant:3000').searchParams.get('order_id'));
  }
  function json(response, status, value) {
    response.writeHead(status, { 'content-type': 'application/json' }).end(JSON.stringify(value));
  }
  function receipt(response, orderId) {
    const order = orders.get(orderId);
    if (!order) return json(response, 404, { error: 'Unknown order' });
    const rows = order.lines.map(line => `<li>${line.quantity} × ${escape(line.name)} · ${money(line.amount)}</li>`).join('');
    response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(
      `<!doctype html><title>Order confirmed</title><h1>Payment confirmed</h1><ul>${rows}<li>${escape(shippingOptions[order.shippingOption].label)} shipping · ${money(order.shippingAmount)}</li></ul><p>Total ${money(order.total)}</p><h2>Shipping destination</h2><address>${Object.values(order.shipping).map(escape).join('<br>')}</address><p>Order ${escape(order.id)}</p>`);
  }
  async function handle(request, response) {
    const path = new URL(request.url || '/', 'http://merchant:3000').pathname;
    if (path === '/catalog' && request.method === 'GET') {
      json(response, 200, {
        currency: 'USD',
        products: [...catalog].map(([sku, product]) => ({ sku, name: product.name, price: (product.amount / 100).toFixed(2) })),
        shippingOptions: Object.entries(shippingOptions).map(([id, option]) => ({ id, label: option.label, detail: option.detail, price: (option.amount / 100).toFixed(2) })),
      });
      return true;
    }
    if (path === '/' && request.method === 'GET') {
      const select = (name, label, options, selected) =>
        `<label for="${name}">${label}</label><select id="${name}" name="${name}">${options.map(([value, text]) => `<option value="${value}"${value === selected ? ' selected' : ''}>${text}</option>`).join('')}</select>`;
      const count = (name, value) => `<label for="${name}">Quantity</label><input id="${name}" name="${name}" type="number" min="0" max="10" value="${value}">`;
      const radios = Object.entries(shippingOptions).map(([id, option]) =>
        `<label class="option"><input type="radio" name="shippingOption" value="${id}"${id === 'express' ? ' checked' : ''}> ${option.label} (${option.detail}) · ${money(option.amount)}</label>`).join('');
      const inputs = Object.entries(fields).map(([name, label]) =>
        `<label for="${name}">${label}</label><input id="${name}" name="${name}" ${name === 'line2' ? '' : 'required'} maxlength="200" autocomplete="shipping ${({ name: 'name', line1: 'address-line1', line2: 'address-line2', city: 'address-level2', state: 'address-level1', postalCode: 'postal-code', country: 'country' })[name]}">`).join('');
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(
        `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Notebook Store</title><style>body{font:16px system-ui;max-width:480px;margin:32px auto}fieldset{margin:0 0 16px}label,input,select{display:block}input,select{box-sizing:border-box;width:100%;padding:8px;margin:4px 0 12px}label.option{display:flex;gap:8px;margin:4px 0}label.option input{width:auto;margin:0}button{padding:12px}</style></head><body><main><h1>Notebook Store</h1><form method="post" action="/shipping"><h2>Products</h2><fieldset><legend>Tempo Notebook · A5 ${money(sizes.a5.amount)} · A4 ${money(sizes.a4.amount)}</legend>${select('notebook_size', 'Size', Object.entries(sizes).map(([value, size]) => [value, `${size.label} · ${money(size.amount)}`]), 'a4')}${select('notebook_ruling', 'Pages', Object.entries(rulings), 'lined')}${count('notebook_quantity', 1)}</fieldset><fieldset><legend>Tempo Pen · ${money(catalog.get('pen').amount)}</legend>${count('pen_quantity', 0)}</fieldset><fieldset><legend>Tempo Sticker Pack · ${money(catalog.get('stickers').amount)}</legend>${count('stickers_quantity', 0)}</fieldset><h2>Shipping method</h2><fieldset>${radios}</fieldset><h2>Shipping address</h2>${inputs}<button>Continue to payment</button></form><p>API clients can GET /catalog for skus, prices and shipping options, then POST JSON to /shipping with Content-Type: application/json, an items array of { sku, quantity }, a shippingOption id, and a shipping object containing name, line1, line2, city, state, postalCode, country. The response includes the order total. Follow the returned paymentUrl to pay.</p></main></body></html>`);
      return true;
    }
    if (path !== '/shipping' || request.method !== 'POST') return false;
    try {
      let body = '';
      for await (const chunk of request) {
        body += chunk;
        if (Buffer.byteLength(body) > 8192) throw new Error('Shipping request too large');
      }
      const isJson = request.headers['content-type']?.split(';')[0].trim().toLowerCase() === 'application/json';
      if (!isJson && body.trimStart().startsWith('{')) throw new Error('Use Content-Type: application/json for JSON shipping requests');
      const parsed = isJson ? JSON.parse(body) : Object.fromEntries(new URLSearchParams(body));
      const input = isJson ? parsed?.shipping : parsed;
      if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('Provide shipping fields');
      const shipping = {};
      for (const field of Object.keys(fields)) {
        const value = input[field] ?? (field === 'line2' ? '' : null);
        if (typeof value !== 'string' || value.length > 200 || (field !== 'line2' && !value.trim())) throw new Error(`Invalid shipping field: ${field}`);
        shipping[field] = value.trim();
      }
      // Validate input shape, never the task's expected cart or address.
      // Incorrect valid orders can be purchased and must fail verification.
      if (!/^[A-Za-z]{2}$/.test(shipping.country)) throw new Error('Use a two-letter country code');
      const orderLines = lines(isJson ? parsed.items : formItems(parsed));
      const shippingOption = parsed.shippingOption;
      if (!Object.hasOwn(shippingOptions, shippingOption ?? '')) throw new Error('Choose a shippingOption: express or standard');
      const shippingAmount = shippingOptions[shippingOption].amount;
      const total = orderLines.reduce((sum, line) => sum + line.amount, shippingAmount);
      // ASCII only: MPP challenges carry the description in a header.
      const description = `${orderLines.map(line => `${line.quantity} x ${line.name}`).join(', ')}, ${shippingOptions[shippingOption].label} shipping`;
      const order = { id: randomUUID(), shipping, source: isJson ? 'json' : 'form', lines: orderLines, shippingOption, shippingAmount, total, description };
      appendFileSync(file, JSON.stringify(order) + '\n');
      orders.set(order.id, order);
      const paymentUrl = `http://merchant:3000${paymentPath}?order_id=${order.id}`;
      if (isJson) json(response, 201, { orderId: order.id, paymentUrl, items: orderLines, shippingOption, total: (total / 100).toFixed(2), currency: 'USD', shipping: order.shipping });
      else response.writeHead(303, { location: paymentUrl }).end();
    } catch (error) {
      json(response, 400, { error: error.message });
    }
    return true;
  }
  async function stripeReceipt(request, response, kind) {
    try {
      const query = new URL(request.url, 'http://merchant:3000').searchParams;
      const records = readFileSync(`${directory}/${kind}.jsonl`, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line));
      const record = records.find(row => kind === 'sessions' ? row.sessionId === query.get('session_id') : row.orderId === query.get('order_id'));
      if (!record) return json(response, 404, { error: 'Unknown payment' });
      const path = kind === 'sessions' ? `/checkout/sessions/${record.sessionId}` : `/payment_intents/${record.intentId}`;
      const provider = await fetch(`https://api.stripe.com/v1${path}`, { headers: { authorization: `Bearer ${process.env.STRIPE_TEST_SECRET_KEY}` }, signal: AbortSignal.timeout(30000) });
      if (!provider.ok) throw new Error('Stripe confirmation unavailable');
      const payment = await provider.json();
      if (payment.livemode !== false || (kind === 'sessions' ? payment.payment_status !== 'paid' : payment.status !== 'succeeded')) return json(response, 409, { error: 'Payment not confirmed' });
      return receipt(response, record.orderId);
    } catch { return json(response, 502, { error: 'Payment confirmation unavailable' }); }
  }
  async function paypalReceipt(request, response, paypal) {
    try {
      const id = new URL(request.url, 'http://merchant:3000').searchParams.get('order_id');
      const record = readFileSync(`${directory}/orders.jsonl`, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)).find(row => row.orderId === id);
      if (!record) return json(response, 404, { error: 'Unknown payment' });
      const payment = await paypal(`/v2/checkout/orders/${record.paypalOrderId}`);
      if (payment.status !== 'COMPLETED' || payment.purchase_units?.[0]?.payments?.captures?.[0]?.status !== 'COMPLETED') return json(response, 409, { error: 'Payment not confirmed' });
      return receipt(response, record.orderId);
    } catch { return json(response, 502, { error: 'Payment confirmation unavailable' }); }
  }
  return { handle, get, receipt, stripeReceipt, paypalReceipt };
}
