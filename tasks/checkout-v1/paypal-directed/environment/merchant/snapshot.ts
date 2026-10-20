import { readFileSync, writeFileSync } from 'node:fs';

const clientId = process.env.PAYPAL_SANDBOX_CLIENT_ID;
const secret = process.env.PAYPAL_SANDBOX_CLIENT_SECRET;
if (!clientId || !secret) throw new Error('PayPal sandbox merchant credentials are required');
const dir = '/var/log/checkout';
let records: { orderId: string; paypalOrderId: string }[] = [];
try {
  records = readFileSync(`${dir}/orders.jsonl`, 'utf8').trim().split('\n').filter(Boolean).map(JSON.parse);
} catch (error) {
  if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) throw error;
}
const auth = await fetch('https://api-m.sandbox.paypal.com/v1/oauth2/token', {
  method: 'POST',
  headers: { authorization: `Basic ${Buffer.from(`${clientId}:${secret}`).toString('base64')}`, 'content-type': 'application/x-www-form-urlencoded' },
  body: 'grant_type=client_credentials',
  signal: AbortSignal.timeout(30000),
});
if (!auth.ok) throw new Error(`PayPal OAuth failed: ${auth.status}`);
const { access_token } = await auth.json();
const orders = [];
for (const record of records) {
  if (!/^[A-Za-z0-9]+$/.test(record.paypalOrderId)) throw new Error('Invalid PayPal order ID');
  const response = await fetch(`https://api-m.sandbox.paypal.com/v2/checkout/orders/${record.paypalOrderId}`, {
    headers: { authorization: `Bearer ${access_token}` },
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok) throw new Error(`PayPal order retrieval failed: ${response.status}`);
  const order = await response.json();
  const purchase = order.purchase_units?.[0];
  const capture = purchase?.payments?.captures?.[0];
  const paymentMethods = Object.keys(order.payment_source ?? {});
  orders.push({
    orderId: record.orderId,
    id: order.id,
    status: order.status,
    paymentMethodType: paymentMethods.length === 1 ? paymentMethods[0] : null,
    referenceId: purchase?.reference_id,
    customId: purchase?.custom_id,
    description: purchase?.description,
    amount: purchase?.amount ? { currency_code: purchase.amount.currency_code, value: purchase.amount.value } : null,
    items: purchase?.items?.map((item: any) => ({
      name: item.name,
      quantity: item.quantity,
      unit_amount: { currency_code: item.unit_amount?.currency_code, value: item.unit_amount?.value },
    })),
    capture: capture ? {
      id: capture.id,
      status: capture.status,
      amount: { currency_code: capture.amount?.currency_code, value: capture.amount?.value },
    } : null,
    captureCount: purchase?.payments?.captures?.length ?? 0,
  });
}
writeFileSync(`${dir}/snapshot.json`, JSON.stringify({ orders }, null, 2) + '\n');
