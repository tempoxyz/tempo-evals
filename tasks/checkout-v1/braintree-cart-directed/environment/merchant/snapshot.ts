import { readFileSync, writeFileSync } from 'node:fs';
import { directory, gateway, readLog } from './gateway.ts';
import { shippingOrders } from './shipping.js';

const trialId = readFileSync(`${directory}/trial-id`, 'utf8');
const found = new Map<string, any>();
// Search the provider, including successful charges whose HTTP response was lost.
const stream = gateway.transaction.search(search => search.orderId().startsWith(`${trialId}:`));
for await (const transaction of stream) {
  found.set(transaction.id, transaction);
}
// Search indexing can lag a newly completed sale. Direct retrieval is the
// authority for recorded transactions; retain search results to catch charges
// whose response was lost and duplicate payments.
for (const record of readLog('transactions')) {
  const transaction = await gateway.transaction.find(record.transactionId);
  found.set(transaction.id, transaction);
}
const transactions: any[] = [];
for (const transaction of found.values()) {
  const account = await gateway.merchantAccount.find(transaction.merchantAccountId);
  transactions.push({
    id: transaction.id, orderId: transaction.orderId.slice(trialId.length + 1),
    referenceId: transaction.orderId, status: transaction.status, amount: transaction.amount,
    currency: transaction.currencyIsoCode, merchantAccountId: transaction.merchantAccountId,
    merchantCurrency: account.currencyIsoCode, type: transaction.type,
    paymentMethodType: transaction.paymentInstrumentType, refundIds: transaction.refundIds ?? [],
  });
}
writeFileSync(`${directory}/snapshot.json`, JSON.stringify({ provider: 'braintree_sandbox', trialId, shippingOrders: shippingOrders(), transactions, checkoutStartCount: readLog('checkout-starts').length }, null, 2) + '\n');
