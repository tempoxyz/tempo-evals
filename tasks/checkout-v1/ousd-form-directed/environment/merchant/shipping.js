// Shared shipping input and immutable order records for checkout shipping tasks.
import { randomUUID } from 'node:crypto';
import { appendFileSync, mkdirSync, readFileSync } from 'node:fs';

const directory = '/var/log/checkout';
const file = `${directory}/shipping.jsonl`;
const fields = {
  name: 'Recipient name', line1: 'Street address', line2: 'Apartment or suite',
  city: 'City', state: 'State code', postalCode: 'Postal code', country: 'Country code',
};
const escape = value => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
export function shippingOrders() {
  try { return readFileSync(file, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)); }
  catch (error) {
    if (error.code !== 'ENOENT') throw error;
    return [];
  }
}
// total is the order's price in USD cents; rail adapters charge it.
export function createShipping(paymentPath, { total = 1200 } = {}) {
  const price = (total / 100).toFixed(2);
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
    response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(
      `<!doctype html><title>Order confirmed</title><h1>Payment confirmed</h1><p>Tempo Notebook · Quantity 1 · $${escape(price)}</p><h2>Shipping destination</h2><address>${Object.values(order.shipping).map(escape).join('<br>')}</address><p>Order ${escape(order.id)}</p>`);
  }
  async function handle(request, response) {
    const path = new URL(request.url || '/', 'http://merchant:3000').pathname;
    if (path === '/' && request.method === 'GET') {
      const inputs = Object.entries(fields).map(([name, label]) =>
        `<label for="${name}">${label}</label><input id="${name}" name="${name}" ${name === 'line2' ? '' : 'required'} maxlength="200" autocomplete="shipping ${({ name: 'name', line1: 'address-line1', line2: 'address-line2', city: 'address-level2', state: 'address-level1', postalCode: 'postal-code', country: 'country' })[name]}">`).join('');
      response.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }).end(
        `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Notebook Store</title><style>body{font:16px system-ui;max-width:480px;margin:32px auto}label,input{display:block}input{box-sizing:border-box;width:100%;padding:8px;margin:4px 0 12px}button{padding:12px}</style></head><body><main><h1>Tempo Notebook</h1><p>One notebook · $${escape(price)} total, including shipping</p><h2>Shipping address</h2><form method="post" action="/shipping">${inputs}<button>Continue to payment</button></form><p>API clients can POST JSON to /shipping with Content-Type: application/json and a shipping object containing name, line1, line2, city, state, postalCode, country. Follow the returned paymentUrl to pay.</p></main></body></html>`);
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
      const input = isJson ? JSON.parse(body)?.shipping : Object.fromEntries(new URLSearchParams(body));
      if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('Provide shipping fields');
      const shipping = {};
      for (const field of Object.keys(fields)) {
        const value = input[field] ?? (field === 'line2' ? '' : null);
        if (typeof value !== 'string' || value.length > 200 || (field !== 'line2' && !value.trim())) throw new Error(`Invalid shipping field: ${field}`);
        shipping[field] = value.trim();
      }
      // Validate input shape, never the task's expected address. Incorrect valid
      // destinations can be purchased and must fail independent verification.
      if (!/^[A-Za-z]{2}$/.test(shipping.country)) throw new Error('Use a two-letter country code');
      // Rail adapters charge the order's description and total (USD cents).
      const order = { id: randomUUID(), shipping, source: isJson ? 'json' : 'form', description: 'Tempo Notebook', total };
      appendFileSync(file, JSON.stringify(order) + '\n');
      orders.set(order.id, order);
      const paymentUrl = `http://merchant:3000${paymentPath}?order_id=${order.id}`;
      if (isJson) json(response, 201, { orderId: order.id, paymentUrl, shipping: order.shipping });
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
