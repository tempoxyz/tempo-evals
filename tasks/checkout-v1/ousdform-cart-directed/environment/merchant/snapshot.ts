import { shippingOrders } from './shipping.js';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { createPublicClient, http } from 'viem';
import { Chain } from 'viem/tempo';

const dir = '/var/log/checkout';
const { ousd, decimals } = JSON.parse(readFileSync(dir + '/merchant.json', 'utf8'));
const read = (file: string) => existsSync(file) ? readFileSync(file, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)) : [];
const client = createPublicClient({ chain: Chain.testnet, transport: http(process.env.TEMPO_RPC_URL || 'https://rpc.moderato.tempo.xyz') });
const abi = [{ type: 'function', name: 'balanceOf', stateMutability: 'view', inputs: [{ name: 'account', type: 'address' }], outputs: [{ type: 'uint256' }] }] as const;
// Every deposit address the store issued, with its balance read onchain now.
const deposits = await Promise.all(read(dir + '/deposits.jsonl').map(async row => ({
  orderId: row.orderId, address: row.address,
  balance: (await client.readContract({ address: ousd, abi, functionName: 'balanceOf', args: [row.address] })).toString(),
})));
// A payment attempt is a Confirm payment request; confirming before the
// transfer arrives is a retry.
const confirms = read(dir + '/attempts.jsonl').length;
writeFileSync(dir + '/snapshot.json', JSON.stringify({
  shippingOrders: shippingOrders(), ousd, decimals, deposits,
  deliveries: read(dir + '/deliveries.jsonl'),
  paymentAttemptCount: confirms || null,
}, null, 2) + '\n');
