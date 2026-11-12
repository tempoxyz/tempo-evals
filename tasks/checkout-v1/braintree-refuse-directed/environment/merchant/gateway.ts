import braintree from 'braintree';
import { readFileSync } from 'node:fs';

export const directory = '/var/log/checkout';
for (const name of ['BRAINTREE_MERCHANT_ID', 'BRAINTREE_PUBLIC_KEY', 'BRAINTREE_PRIVATE_KEY']) {
  if (!process.env[name]) throw new Error(`Missing ${name}`);
}
// Never allow the benchmark to select a production gateway.
export const gateway = new braintree.BraintreeGateway({
  environment: braintree.Environment.Sandbox,
  merchantId: process.env.BRAINTREE_MERCHANT_ID!,
  publicKey: process.env.BRAINTREE_PUBLIC_KEY!,
  privateKey: process.env.BRAINTREE_PRIVATE_KEY!,
});
export const captured = (status: string) => ['submitted_for_settlement', 'settling', 'settled'].includes(status);
export function readLog(name: string): any[] {
  try { return readFileSync(`${directory}/${name}.jsonl`, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line)); }
  catch (error) {
    if (!(error instanceof Error && 'code' in error && error.code === 'ENOENT')) throw error;
    return [];
  }
}
