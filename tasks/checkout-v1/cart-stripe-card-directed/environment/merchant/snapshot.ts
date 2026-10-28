import { shippingOrders } from './shipping.js';
import { readFileSync, writeFileSync } from 'node:fs';

const key = process.env.STRIPE_TEST_SECRET_KEY;
if (!key?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
const dir = '/var/log/checkout';
let records = [];
try {
  records = readFileSync(`${dir}/sessions.jsonl`, 'utf8').trim().split('\n')
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

const sessions = [];
for (const record of records) {
  if (!/^cs_test_[A-Za-z0-9_]+$/.test(record.sessionId)) throw new Error('Invalid session ID');
  const session = await stripeGet(`/checkout/sessions/${record.sessionId}?expand[]=payment_intent.payment_method`);
  const items = await stripeGet(`/checkout/sessions/${record.sessionId}/line_items?limit=10`);
  sessions.push({
    orderId: record.orderId,
    id: session.id,
    livemode: session.livemode,
    clientReferenceId: session.client_reference_id,
    metadataOrderId: session.metadata?.order_id,
    status: session.status,
    paymentStatus: session.payment_status,
    amountTotal: session.amount_total,
    currency: session.currency,
    paymentIntent: session.payment_intent && typeof session.payment_intent === 'object' ? {
      id: session.payment_intent.id,
      status: session.payment_intent.status,
      amount: session.payment_intent.amount,
      amountReceived: session.payment_intent.amount_received,
      currency: session.payment_intent.currency,
      paymentMethodType: session.payment_intent.payment_method?.type ?? null,
    } : null,
    items: items.data.map((item: { description: string; quantity: number; amount_total: number; currency: string }) => ({
      description: item.description,
      quantity: item.quantity,
      amountTotal: item.amount_total,
      currency: item.currency,
    })),
  });
}
writeFileSync(`${dir}/snapshot.json`, JSON.stringify({ shippingOrders: shippingOrders(), sessions }, null, 2) + '\n');
