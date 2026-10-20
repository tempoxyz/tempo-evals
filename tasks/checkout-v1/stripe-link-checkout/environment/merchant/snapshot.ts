import { readFileSync, writeFileSync } from 'node:fs';

const key = process.env.STRIPE_TEST_SECRET_KEY;
if (!key?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
const dir = '/var/log/checkout';
let records = [];
try {
  records = readFileSync(`${dir}/intents.jsonl`, 'utf8').trim().split('\n')
    .filter(Boolean).map(line => JSON.parse(line));
} catch (error) {
  if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) throw error;
}

async function stripeGet(path: string) {
  const response = await fetch(`https://api.stripe.com/v1${path}`, {
    headers: { authorization: `Bearer ${key}` },
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error(`Stripe retrieval failed: ${response.status}`);
  return response.json();
}

const intents = [];
for (const record of records) {
  if (!/^pi_[A-Za-z0-9]+$/.test(record.intentId)) throw new Error('Invalid intent ID');
  const intent = await stripeGet(`/payment_intents/${record.intentId}?expand[]=payment_method`);
  intents.push({
    orderId: record.orderId,
    id: intent.id,
    livemode: intent.livemode,
    metadataOrderId: intent.metadata?.order_id,
    item: intent.metadata?.item,
    description: intent.description,
    status: intent.status,
    amount: intent.amount,
    amountReceived: intent.amount_received,
    currency: intent.currency,
    paymentMethodTypes: intent.payment_method_types,
    paymentMethodType: intent.payment_method?.type ?? null,
  });
}
writeFileSync(`${dir}/snapshot.json`, JSON.stringify({ intents }, null, 2) + '\n');
