import assert from 'node:assert/strict';
import { test } from 'node:test';
import { challengeCharges, pageCharges, paymentAsset } from './oracle.ts';

const encode = (value: object) => Buffer.from(JSON.stringify(value)).toString('base64url');
const ousd = '0x20c0000000000000000000006a37DA5C996874BE';
const usdc = '0x036CbD53842c5426634e7929541eC2318f3dCF7e';

test('reads the charge and the token from an x402 challenge', () => {
  const headers = new Headers({ 'payment-required': encode({ accepts: [{ amount: '12000000', asset: usdc, network: 'eip155:84532' }] }) });
  assert.deepEqual(challengeCharges(headers), [1200]);
  assert.deepEqual(paymentAsset(headers), { chain: 'baseSepolia', token: usdc });
});

test('reads the charge and the token from an MPP OUSD challenge', () => {
  const headers = new Headers({ 'www-authenticate': `Payment id="1", method="tempo", request="${encode({ amount: '12000000', currency: ousd })}"` });
  assert.deepEqual(challengeCharges(headers), [1200]);
  assert.deepEqual(paymentAsset(headers), { chain: 'tempo', token: ousd });
});

test('reads the charge and the token from the OUSD form page', () => {
  const html = `<p>Send exactly <strong data-amount="12.00">12.00 OUSD</strong></p><code data-token="${ousd}">${ousd}</code>`;
  assert.deepEqual(pageCharges(html), [1200]);
  assert.deepEqual(paymentAsset(new Headers(), html), { chain: 'tempo', token: ousd });
});

test('a card challenge names no stablecoin', () => {
  const headers = new Headers({ 'www-authenticate': `Payment request="${encode({ amount: '1200', currency: 'usd' })}"` });
  assert.deepEqual(challengeCharges(headers), [1200]);
  assert.equal(paymentAsset(headers), null);
});
