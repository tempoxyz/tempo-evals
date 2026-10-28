import { shippingOrders } from './shipping.js';
import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { decodeEventLog } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
import { Receipt, x402 } from 'mppx';
import { balanceOf, client, transfer } from './x402.js';

const dir = '/var/log/checkout';
const { recipient, usdc, buyer } = JSON.parse(readFileSync(`${dir}/merchant.json`, 'utf8'));
function lines(name: string) {
  try {
    return readFileSync(`${dir}/${name}`, 'utf8').trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
  } catch (error) {
    if (error instanceof Error && 'code' in error && error.code === 'ENOENT') return null;
    throw error;
  }
}
const records: { orderId: string; item: string; quantity: number; amount: string; currency: string; receipt: string | null; paymentResponse: string | null }[] = lines('deliveries.jsonl') ?? [];
const attempts = lines('attempts.jsonl');
const paymentAttemptCount = attempts ? attempts.filter(record => record.paymentAttempt === true).length : null;
const transferAbi = [{
  type: 'event', name: 'Transfer',
  inputs: [{ name: 'from', type: 'address', indexed: true }, { name: 'to', type: 'address', indexed: true }, { name: 'value', type: 'uint256', indexed: false }],
}] as const;
const deliveries = [];
for (const record of records) {
  let settlement = null;
  try {
    if (record.paymentResponse) settlement = x402.Header.decodePaymentResponse(record.paymentResponse);
  } catch { /* A malformed settlement is an unverified delivery. */ }
  let receipt = null;
  try {
    if (record.receipt) receipt = Receipt.deserialize(record.receipt);
  } catch { /* A malformed receipt is an unverified delivery. */ }
  let txStatus = null;
  let transfers: { from: string; to: string; value: string }[] = [];
  if (settlement && /^0x[0-9a-fA-F]{64}$/.test(settlement.transaction)) {
    try {
      // The facilitator can answer before the RPC indexes its receipt.
      const tx = await client.waitForTransactionReceipt({ hash: settlement.transaction as `0x${string}`, timeout: 30_000 });
      txStatus = tx.status;
      transfers = tx.logs.filter(log => log.address.toLowerCase() === usdc.toLowerCase()).flatMap(log => {
        try {
          const event = decodeEventLog({ abi: transferAbi, data: log.data, topics: log.topics });
          return [{ from: event.args.from, to: event.args.to, value: event.args.value.toString() }];
        } catch { return []; }
      });
    } catch (error) {
      // Fail collection so its retry runs, rather than recording a valid
      // payment as unconfirmed.
      throw new Error(`Settlement receipt unavailable: ${error instanceof Error ? error.message : error}`);
    }
  }
  deliveries.push({
    orderId: record.orderId, item: record.item, quantity: record.quantity, amount: record.amount, currency: record.currency,
    receiptStatus: settlement?.success && receipt?.status === 'success' ? 'success' : receipt?.status ?? null,
    receiptMethod: settlement ? 'x402' : null,
    settlement: settlement && { success: settlement.success, network: settlement.network, payer: settlement.payer, transaction: settlement.transaction },
    txStatus, transfers,
  });
}

// Record the buyer's remaining balance once and write the evidence before the
// best-effort return of that balance to the funding wallet, which is bounded
// below the collection timeout. A repeated collection reuses the observation.
let recovery = existsSync(`${dir}/recovery.json`) ? JSON.parse(readFileSync(`${dir}/recovery.json`, 'utf8')) : null;
if (!recovery) {
  recovery = { buyerBalance: (await balanceOf(buyer)).toString(), transaction: null as string | null, error: null as string | null };
  writeFileSync(`${dir}/recovery.json`, JSON.stringify(recovery));
}
function writeSnapshot() {
  writeFileSync(`${dir}/snapshot.json`, JSON.stringify({
    shippingOrders: shippingOrders(), recipient, usdc, buyer, deliveries, paymentAttemptCount,
    buyerBalanceAfterAgent: recovery.buyerBalance, recoveryTransaction: recovery.transaction,
  }, null, 2) + '\n');
}
writeSnapshot();
if (!recovery.transaction) {
  const remaining = await balanceOf(buyer).catch(() => 0n);
  if (remaining > 0n) {
    try {
      const wallet = JSON.parse(readFileSync('/wallet/wallet.json', 'utf8'));
      recovery.transaction = await transfer(privateKeyToAccount(wallet.baseSepolia.privateKey), recipient, remaining, AbortSignal.timeout(25_000));
      recovery.error = null;
    } catch (error) {
      recovery.error = error instanceof Error ? error.message : String(error);
    }
    writeFileSync(`${dir}/recovery.json`, JSON.stringify(recovery));
    writeSnapshot();
  }
}
