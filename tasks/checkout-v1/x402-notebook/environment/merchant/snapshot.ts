import { readFileSync, writeFileSync } from 'node:fs';
import { createPublicClient, decodeEventLog, http } from 'viem';
import { baseSepolia } from 'viem/chains';
import { x402 } from 'mppx';

const dir = '/var/log/checkout';
const { recipient, usdc } = JSON.parse(readFileSync(`${dir}/merchant.json`, 'utf8'));
let records: { orderId: string; item: string; quantity: number; amount: string; currency: string; paymentResponse: string }[] = [];
try {
  records = readFileSync(`${dir}/deliveries.jsonl`, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
} catch (error) {
  if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) throw error;
}
const client = createPublicClient({ chain: baseSepolia, transport: http(process.env.BASE_SEPOLIA_RPC_URL || 'https://sepolia.base.org') });
const transferAbi = [{
  type: 'event', name: 'Transfer',
  inputs: [
    { name: 'from', type: 'address', indexed: true },
    { name: 'to', type: 'address', indexed: true },
    { name: 'value', type: 'uint256', indexed: false },
  ],
}] as const;
const deliveries = [];
for (const record of records) {
  let settlement = null;
  try {
    if (record.paymentResponse) settlement = x402.Header.decodePaymentResponse(record.paymentResponse);
  } catch { /* A malformed settlement is an unverified delivery. */ }
  let txStatus = null;
  let transfers: { from: string; to: string; value: string }[] = [];
  if (settlement && /^0x[0-9a-fA-F]{64}$/.test(settlement.transaction)) {
    try {
      const tx = await client.waitForTransactionReceipt({ hash: settlement.transaction as `0x${string}`, timeout: 75_000 });
      txStatus = tx.status;
      transfers = tx.logs.filter(log => log.address.toLowerCase() === usdc.toLowerCase()).flatMap(log => {
        try {
          const event = decodeEventLog({ abi: transferAbi, data: log.data, topics: log.topics });
          if (event.eventName !== 'Transfer') return [];
          return [{ from: event.args.from, to: event.args.to, value: event.args.value.toString() }];
        } catch { return []; }
      });
    } catch (error) { throw new Error('Could not confirm x402 settlement transaction', { cause: error }); }
  }
  deliveries.push({
    orderId: record.orderId,
    item: record.item,
    quantity: record.quantity,
    amount: record.amount,
    currency: record.currency,
    settlement: settlement && {
      success: settlement.success,
      network: settlement.network,
      payer: settlement.payer,
      amount: settlement.amount,
      transaction: settlement.transaction,
    },
    txStatus,
    transfers,
  });
}
const key = process.env.STRIPE_TEST_SECRET_KEY;
if (!key?.startsWith('sk_test_')) throw new Error('A Stripe sandbox secret key is required');
let cardRecords: { orderId: string; paymentIntentId: string }[] = [];
try {
  cardRecords = readFileSync(`${dir}/card-orders.jsonl`, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
} catch (error) {
  if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) throw error;
}
const cardOrders = [];
for (const record of cardRecords) {
  if (!/^pi_[A-Za-z0-9_]+$/.test(record.paymentIntentId)) throw new Error('Invalid PaymentIntent ID');
  const response = await fetch(`https://api.stripe.com/v1/payment_intents/${record.paymentIntentId}?expand[]=payment_method`, {
    headers: { authorization: `Bearer ${key}` },
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error(`Stripe retrieval failed: ${response.status}`);
  const intent = await response.json();
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
writeFileSync(`${dir}/snapshot.json`, JSON.stringify({ recipient, usdc, deliveries, cardOrders }, null, 2) + '\n');
