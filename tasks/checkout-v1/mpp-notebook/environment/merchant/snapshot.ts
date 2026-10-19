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
let cardRecords: { orderId: string; paymentIntentId: string }[] = [];
try {
  cardRecords = readFileSync(`${dir}/card-orders.jsonl`, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
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
const cardOrders = [];
for (const record of cardRecords) {
  if (!/^pi_[A-Za-z0-9_]+$/.test(record.paymentIntentId)) throw new Error('Invalid PaymentIntent ID');
  const intent = await stripeGet(`/payment_intents/${record.paymentIntentId}?expand[]=payment_method`);
  cardOrders.push({
    orderId: record.orderId,
    id: intent.id,
    livemode: intent.livemode,
    metadataOrderId: intent.metadata?.order_id,
    metadataItem: intent.metadata?.item,
    metadataQuantity: intent.metadata?.quantity,
    status: intent.status,
    amount: intent.amount,
    amountReceived: intent.amount_received,
    currency: intent.currency,
    paymentMethodType: intent.payment_method?.type ?? null,
  });
}
writeFileSync(`${dir}/snapshot.json`, JSON.stringify({ recipient, pathUsd, balance: balance.toString(), decimals, deliveries, cardOrders }, null, 2) + '\n');
