import { readFileSync, writeFileSync } from 'node:fs';
import { createPublicClient, http } from 'viem';
import { Chain } from 'viem/tempo';
import { Receipt } from 'mppx';

const dir = '/var/log/checkout';
const { recipient, pathUsd } = JSON.parse(readFileSync(`${dir}/merchant.json`, 'utf8'));
let records: { orderId: string; receipt: string }[] = [];
try {
  records = readFileSync(`${dir}/deliveries.jsonl`, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
} catch (error) {
  if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) throw error;
}
const client = createPublicClient({ chain: Chain.testnet, transport: http(process.env.TEMPO_RPC_URL || 'https://rpc.moderato.tempo.xyz') });
const abi = [
  { type: 'function', name: 'balanceOf', stateMutability: 'view', inputs: [{ name: 'account', type: 'address' }], outputs: [{ type: 'uint256' }] },
  { type: 'function', name: 'decimals', stateMutability: 'view', inputs: [], outputs: [{ type: 'uint8' }] },
] as const;
const balance = await client.readContract({ address: pathUsd, abi, functionName: 'balanceOf', args: [recipient] });
const decimals = await client.readContract({ address: pathUsd, abi, functionName: 'decimals' });
const deliveries = records.map(record => {
  const receipt = record.receipt ? Receipt.deserialize(record.receipt) : null;
  return { orderId: record.orderId, receiptStatus: receipt?.status ?? null, receiptMethod: receipt?.method ?? null };
});
const key = process.env.STRIPE_TEST_SECRET_KEY;
if (!key?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
let sessionRecords: { orderId: string; sessionId: string }[] = [];
try {
  sessionRecords = readFileSync(`${dir}/sessions.jsonl`, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
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
for (const record of sessionRecords) {
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
writeFileSync(`${dir}/snapshot.json`, JSON.stringify({ recipient, pathUsd, balance: balance.toString(), decimals, deliveries, sessions }, null, 2) + '\n');
