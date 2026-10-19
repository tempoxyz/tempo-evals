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
      const tx = await client.getTransactionReceipt({ hash: settlement.transaction as `0x${string}` });
      txStatus = tx.status;
      transfers = tx.logs.filter(log => log.address.toLowerCase() === usdc.toLowerCase()).flatMap(log => {
        try {
          const event = decodeEventLog({ abi: transferAbi, data: log.data, topics: log.topics });
          if (event.eventName !== 'Transfer') return [];
          return [{ from: event.args.from, to: event.args.to, value: event.args.value.toString() }];
        } catch { return []; }
      });
    } catch { /* An unconfirmed transaction cannot verify the order. */ }
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
writeFileSync(`${dir}/snapshot.json`, JSON.stringify({ recipient, usdc, deliveries }, null, 2) + '\n');
