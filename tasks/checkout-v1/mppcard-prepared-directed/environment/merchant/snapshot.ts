import { shippingOrders } from './shipping.js';
import { readFileSync, writeFileSync } from 'node:fs';
import { Receipt } from 'mppx';

const key = process.env.STRIPE_TEST_SECRET_KEY;
if (!key?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
const dir = '/var/log/checkout';
const merchant = JSON.parse(readFileSync(`${dir}/merchant.json`, 'utf8'));
function records(name: string): Record<string, any>[] {
  try {
    return readFileSync(`${dir}/${name}.jsonl`, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line));
  } catch (error) {
    if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) throw error;
    return [];
  }
}
async function stripeGet(path: string) {
  const response = await fetch(`https://api.stripe.com/v1${path}`, {
    headers: { authorization: `Bearer ${key}` }, signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error(`Stripe retrieval failed: ${response.status}`);
  return response.json();
}

// List provider-side intents too: a charge without a delivered order must fail.
const payments = [];
let cursor = '';
do {
  const page = await stripeGet(`/payment_intents?limit=100&created[gte]=${merchant.startedAt}${cursor ? `&starting_after=${cursor}` : ''}`);
  for (const intent of page.data) {
    if (intent.metadata?.checkout_trial_id !== merchant.trialId) continue;
    const verified = await stripeGet(`/payment_intents/${intent.id}?expand[]=payment_method&expand[]=latest_charge`);
    const charge = verified.latest_charge;
    payments.push({
      id: verified.id, livemode: verified.livemode, status: verified.status,
      amount: verified.amount, amountReceived: verified.amount_received, currency: verified.currency,
      trialId: verified.metadata?.checkout_trial_id, orderId: verified.metadata?.order_id,
      paymentMethodType: verified.payment_method?.type,
      charge: charge ? {
        id: charge.id, livemode: charge.livemode, status: charge.status,
        paid: charge.paid, captured: charge.captured, refunded: charge.refunded,
        amount: charge.amount, amountCaptured: charge.amount_captured, amountRefunded: charge.amount_refunded,
        currency: charge.currency, paymentIntent: charge.payment_intent,
        paymentMethodType: charge.payment_method_details?.type,
      } : null,
    });
  }
  cursor = page.has_more ? page.data.at(-1).id : '';
} while (cursor);
const deliveries = records('deliveries').map(record => {
  const receipt = record.receipt ? Receipt.deserialize(record.receipt) : null;
  return {
    orderId: record.orderId, item: record.item, quantity: record.quantity, amount: record.amount, currency: record.currency,
    receiptStatus: receipt?.status, receiptMethod: receipt?.method, receiptReference: receipt?.reference,
  };
});
const paymentAttemptCount = records('attempts').filter(record => record.paymentAttempt === true).length;
writeFileSync(`${dir}/snapshot.json`, JSON.stringify({ shippingOrders: shippingOrders(), ...merchant, orderId: deliveries[0]?.orderId, payments, deliveries, paymentAttemptCount }, null, 2) + '\n');
