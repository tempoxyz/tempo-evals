import { readFileSync, writeFileSync } from 'node:fs';
import { directory, gateway, readLog } from './gateway.ts';
import { shippingOrders } from './shipping.js';

const trialId = readFileSync(`${directory}/trial-id`, 'utf8');
const transactions: any[] = [];
// Search the provider, including successful charges whose HTTP response was lost.
const stream = gateway.transaction.search(search => search.orderId().startsWith(`${trialId}:`));
for await (const transaction of stream) {
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
