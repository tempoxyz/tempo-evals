import { randomInt } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';

const key = process.env.STRIPE_TEST_SECRET_KEY;
if (!key?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
const wallet = JSON.parse(readFileSync('/wallet/wallet.json', 'utf8'));
const base = 'http://merchant:3000';
let browserSession;
let nextId = 1;

async function browserRpc(method, params, notification = false) {
  const id = notification ? undefined : nextId++;
  const response = await fetch('http://browser:8931/mcp', {
    method: 'POST',
    headers: {
      accept: 'application/json, text/event-stream',
      'content-type': 'application/json',
      'mcp-protocol-version': '2025-03-26',
      ...(browserSession ? { 'mcp-session-id': browserSession } : {}),
    },
    body: JSON.stringify({ jsonrpc: '2.0', ...(id === undefined ? {} : { id }), method, params }),
    signal: AbortSignal.timeout(90000),
  });
  browserSession = response.headers.get('mcp-session-id') || browserSession;
  if (!response.ok) throw new Error(`Browser MCP ${method} failed: ${response.status}`);
  if (notification) return;
  const body = await response.text();
  const messages = response.headers.get('content-type')?.includes('text/event-stream')
    ? body.split('\n').filter(line => line.startsWith('data:')).map(line => JSON.parse(line.slice(5)))
    : [JSON.parse(body)];
  const message = messages.find(value => value.id === id);
  if (!message || message.error) throw new Error(`Browser MCP ${method} returned an error`);
  return message.result;
}

async function stripe(path, options = {}) {
  const response = await fetch(`https://api.stripe.com/v1${path}`, {
    ...options,
    headers: {
      authorization: `Bearer ${key}`,
      ...(options.body ? { 'content-type': 'application/x-www-form-urlencoded' } : {}),
    },
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error(`Stripe setup request failed: ${response.status}`);
  return response.json();
}

async function main() {
  await browserRpc('initialize', {
    protocolVersion: '2025-03-26',
    capabilities: {},
    clientInfo: { name: 'checkout-link-setup', version: '1.0.0' },
  });
  await browserRpc('notifications/initialized', {}, true);
  const tools = await browserRpc('tools/list', {});
  if (!tools.tools.some(tool => tool.name === 'browser_run_code_unsafe')) {
    throw new Error('Pinned browser lacks browser_run_code_unsafe');
  }
  const card = wallet.card;
  const triedPhones = new Set();
  for (let attempt = 0; attempt < 3; attempt++) {
    let phone = wallet.link.phone;
    while (triedPhones.has(phone)) {
      phone = wallet.link.phone.slice(0, 8) + String(randomInt(100)).padStart(2, '0');
    }
    triedPhones.add(phone);
    const form = new URLSearchParams({
      mode: 'setup',
      currency: 'usd',
      'payment_method_types[0]': 'card',
      'payment_method_types[1]': 'link',
      customer_email: wallet.link.email,
      success_url: `${base}/`,
      cancel_url: `${base}/`,
    });
    const session = await stripe('/checkout/sessions', { method: 'POST', body: form });
    if (!session.id?.startsWith('cs_test_') || !session.url || session.livemode !== false) {
      throw new Error('Stripe did not create a sandbox Link setup session');
    }
    const script = `async (page) => {
    await page.goto(${JSON.stringify(session.url)});
    const fill = async (name, value, optional = false) => {
      for (let attempt = 0; attempt < (optional ? 4 : 60); attempt++) {
        for (const frame of [page, ...page.frames()]) {
          const field = frame.getByRole('textbox', { name }).first();
          if (await field.count()) { await field.fill(value); return; }
        }
        await page.waitForTimeout(500);
      }
      if (!optional) throw new Error('Missing Link setup field: ' + name);
    };
    await fill('Card number', ${JSON.stringify(card.number)});
    await fill('Expiration', ${JSON.stringify(card.expMonth + String(card.expYear).slice(-2))});
    await fill(/CVC/, ${JSON.stringify(card.cvc)});
    await fill('Cardholder name', 'Tempo Test Buyer');
    await page.getByRole('combobox', { name: 'Country or region' }).selectOption('US');
    await fill(/ZIP|Postal code/i, '94103', true);
    const saveWithLink = page.getByRole('checkbox', { name: /Save my information/i });
    await saveWithLink.waitFor({ state: 'visible', timeout: 30000 });
    await saveWithLink.check();
    await page.getByRole('combobox', { name: 'Phone number country code' }).selectOption('US');
    await page.getByRole('textbox', { name: 'Phone number' }).fill(${JSON.stringify(phone)});
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await page.waitForURL(${JSON.stringify(base + '/')}, { timeout: 60000 });
    return 'Link setup returned to merchant';
  }`;
    const result = await browserRpc('tools/call', {
      name: 'browser_run_code_unsafe', arguments: { code: script },
    });
    if (result.isError) {
      const detail = result.content?.find(item => item.type === 'text')?.text || '';
      console.warn(detail.split('\n').find(line => line.includes('Error:')) || 'Link browser setup returned an error');
    }

    const verified = await stripe(`/checkout/sessions/${session.id}?expand[]=setup_intent.payment_method`);
    const setup = verified.setup_intent;
    const paymentMethod = setup?.payment_method;
    if (
      verified.livemode !== false || verified.mode !== 'setup' || verified.status !== 'complete'
      || setup?.status !== 'succeeded' || paymentMethod?.livemode !== false
      || paymentMethod?.type !== 'link' || paymentMethod.link?.email !== wallet.link.email
    ) continue;

    const closed = await browserRpc('tools/call', { name: 'browser_close', arguments: {} });
    if (closed.isError) throw new Error('Link setup browser did not close');
    wallet.link.phone = phone;
    writeFileSync('/wallet/wallet.json', JSON.stringify(wallet, null, 2) + '\n');
    writeFileSync('/wallet/link-ready', '');
    console.log('Trial Link sandbox identity enrolled and verified');
    return;
  }
  throw new Error('Link enrollment did not succeed with three trial phone numbers');
}

main().catch(error => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
