import { readFileSync } from 'node:fs';

const key = process.env.STRIPE_TEST_SECRET_KEY;
if (!key?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
const wallet = JSON.parse(readFileSync('/wallet/wallet.json', 'utf8'));
const base = process.env.PUBLIC_BASE_URL || 'http://merchant:3000';
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
  const form = new URLSearchParams({
    mode: 'setup',
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
  const script = `async (page) => {
    await page.goto(${JSON.stringify(session.url)});
    await page.getByRole('textbox', { name: 'Card number' }).fill(${JSON.stringify(card.number)});
    await page.getByRole('textbox', { name: 'Expiration' }).fill(${JSON.stringify(card.expMonth + String(card.expYear).slice(-2))});
    await page.getByRole('textbox', { name: /CVC/ }).fill(${JSON.stringify(card.cvc)});
    await page.getByRole('textbox', { name: 'Cardholder name' }).fill('Tempo Test Buyer');
    await page.getByRole('textbox', { name: 'ZIP' }).fill('94103');
    const saveWithLink = page.getByRole('checkbox', { name: /Save my information with Link/ });
    if (!await saveWithLink.isVisible()) throw new Error('Link enrollment is unavailable');
    await saveWithLink.check();
    await page.getByRole('textbox', { name: 'Phone number' }).fill(${JSON.stringify(wallet.link.phone)});
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await page.waitForURL(${JSON.stringify(base + '/')}, { timeout: 60000 });
    return 'Link setup returned to merchant';
  }`;
  const result = await browserRpc('tools/call', {
    name: 'browser_run_code_unsafe', arguments: { code: script },
  });
  if (result.isError) throw new Error('Browser Link enrollment failed');

  const verified = await stripe(`/checkout/sessions/${session.id}?expand[]=setup_intent.payment_method`);
  const setup = verified.setup_intent;
  const paymentMethod = setup?.payment_method;
  if (
    verified.livemode !== false || verified.mode !== 'setup' || verified.status !== 'complete'
    || setup?.status !== 'succeeded' || paymentMethod?.livemode !== false
    || paymentMethod?.type !== 'link' || paymentMethod.link?.email !== wallet.link.email
  ) {
    throw new Error('Stripe did not verify an isolated Link account with a saved test card');
  }
  console.log('Trial Link sandbox identity enrolled and verified');
}

main().catch(error => {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
});
