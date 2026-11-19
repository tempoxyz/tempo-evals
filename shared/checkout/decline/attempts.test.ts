import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { copyFileSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const tsx = join(here, '../../../node_modules/.bin/tsx');

// Runs attempts.ts on a fixture snapshot, with fetch or the Braintree gateway faked.
function run(snapshot: object, files: Record<string, string>, env: Record<string, string> = {}) {
  const dir = mkdtempSync(join(tmpdir(), 'checkout-attempts-'));
  copyFileSync(join(here, 'attempts.ts'), join(dir, 'attempts.ts'));
  writeFileSync(join(dir, 'package.json'), JSON.stringify({ type: 'module' }));
  writeFileSync(join(dir, 'snapshot.json'), JSON.stringify(snapshot));
  for (const [name, content] of Object.entries(files)) writeFileSync(join(dir, name), content);
  const preload = files['stub.mjs'] ? ['--import', join(dir, 'stub.mjs')] : [];
  execFileSync(tsx, [...preload, join(dir, 'attempts.ts')], { env: { ...process.env, CHECKOUT_LOG_DIR: dir, ...env }, stdio: 'pipe' });
  return JSON.parse(readFileSync(join(dir, 'snapshot.json'), 'utf8'));
}

test('lists every Stripe charge on the trial PaymentIntents with its card', () => {
  const charges = {
    pi_session: [
      { id: 'ch_paid', livemode: false, status: 'succeeded', payment_method_details: { card: { last4: '4444' } } },
      { id: 'ch_declined', livemode: false, status: 'failed', payment_method_details: { card: { last4: '0002' } } },
    ],
    pi_token: [{ id: 'ch_pending', livemode: false, status: 'pending', payment_method_details: { card: { last4: '4444' } } }],
  };
  const stub = `const charges = ${JSON.stringify(charges)};
globalThis.fetch = async (url, init) => {
  const intent = new URL(url).searchParams.get('payment_intent');
  if (init.headers.authorization !== 'Bearer sk_test_fake' || !(intent in charges)) return new Response('{}', { status: 404 });
  return new Response(JSON.stringify({ data: charges[intent], has_more: false }));
};`;
  const snapshot = run({
    shippingOrders: [],
    sessions: [{ orderId: 'order-1', paymentIntent: { id: 'pi_session' } }, { orderId: 'order-2', paymentIntent: null }],
    payments: [{ id: 'pi_token', orderId: 'order-3' }],
  }, { 'stub.mjs': stub }, { STRIPE_TEST_SECRET_KEY: 'sk_test_fake' });
  assert.deepEqual(snapshot.cardAttempts, [
    { kind: 'charge', id: 'ch_paid', orderId: 'order-1', status: 'succeeded', outcome: 'succeeded', last4: '4444' },
    { kind: 'charge', id: 'ch_declined', orderId: 'order-1', status: 'failed', outcome: 'declined', last4: '0002' },
    { kind: 'charge', id: 'ch_pending', orderId: 'order-3', status: 'pending', outcome: 'other', last4: '4444' },
  ]);
  assert.deepEqual(snapshot.sessions[0], { orderId: 'order-1', paymentIntent: { id: 'pi_session' } });
});

test('lists Braintree sales and failed card verifications with their cards', () => {
  const gateway = String.raw`import { readFileSync } from 'node:fs';
const transactions = { sale: { id: 'sale', status: 'submitted_for_settlement', creditCard: { last4: '4444' } } };
const verifications = { declined: { id: 'declined', status: 'processor_declined', creditCard: { last4: '1115' } } };
export const gateway = {
  transaction: { find: async (id) => transactions[id] },
  creditCardVerification: { find: async (id) => verifications[id] },
};
export function readLog(name) {
  return readFileSync(process.env.CHECKOUT_LOG_DIR + '/' + name + '.jsonl', 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line));
}`;
  const snapshot = run(
    { provider: 'braintree_sandbox', shippingOrders: [], transactions: [{ id: 'sale', orderId: 'order-2' }] },
    {
      'gateway.ts': gateway,
      'declines.jsonl': JSON.stringify({ orderId: 'order-1', verificationId: 'declined' }) + '\n' + JSON.stringify({ orderId: 'order-1', verificationId: null }) + '\n',
    },
  );
  assert.deepEqual(snapshot.cardAttempts, [
    { kind: 'transaction', id: 'sale', orderId: 'order-2', status: 'submitted_for_settlement', outcome: 'succeeded', last4: '4444' },
    { kind: 'verification', id: 'declined', orderId: 'order-1', status: 'processor_declined', outcome: 'declined', last4: '1115' },
  ]);
});
