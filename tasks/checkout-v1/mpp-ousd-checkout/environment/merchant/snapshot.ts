import { readFileSync, writeFileSync } from 'node:fs';
import { createPublicClient, http } from 'viem';
import { Chain } from 'viem/tempo';
import { Receipt } from 'mppx';

const dir = '/var/log/checkout';
const { recipient, ousd } = JSON.parse(readFileSync(`${dir}/merchant.json`, 'utf8'));
let records: { orderId: string; item: string; quantity: number; amount: string; currency: string; receipt: string }[] = [];
let checkoutRequestCount = 0;
try {
  checkoutRequestCount = readFileSync(`${dir}/attempts.jsonl`, 'utf8').trim().split('\n').filter(Boolean).length;
} catch (error) {
  if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) throw error;
}
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
const balance = await client.readContract({ address: ousd, abi, functionName: 'balanceOf', args: [recipient] });
const decimals = await client.readContract({ address: ousd, abi, functionName: 'decimals' });
const deliveries = records.map(record => {
  const receipt = record.receipt ? Receipt.deserialize(record.receipt) : null;
  return {
    orderId: record.orderId, item: record.item, quantity: record.quantity,
    amount: record.amount, currency: record.currency,
    receiptStatus: receipt?.status ?? null, receiptMethod: receipt?.method ?? null,
  };
});
writeFileSync(`${dir}/snapshot.json`, JSON.stringify({ recipient, ousd, balance: balance.toString(), decimals, deliveries, checkoutRequestCount }, null, 2) + '\n');
