import { readFileSync } from 'node:fs';
import { setTimeout } from 'node:timers/promises';
import { createPublicClient, http } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
import { baseSepolia } from 'viem/chains';
import { Mppx, evm } from 'mppx/client';

const url = process.argv[2];
if (!url?.startsWith('http://merchant:3000/')) throw new Error('Provide a merchant purchase URL');
const wallet = JSON.parse(readFileSync('/wallet/wallet.json', 'utf8'));
const account = privateKeyToAccount(wallet.baseSepolia.privateKey);
const client = createPublicClient({ chain: baseSepolia, transport: http(wallet.baseSepolia.rpcUrl) });
const balanceOf = [{
  type: 'function', name: 'balanceOf', stateMutability: 'view',
  inputs: [{ name: 'account', type: 'address' }], outputs: [{ type: 'uint256' }],
}] as const;
const mppx = Mppx.create({
  methods: [evm.charge({
    account,
    currencies: [evm.assets.baseSepolia.USDC],
    maxAmount: '12',
    networks: [84532],
  })],
  polyfill: false,
});
async function main() {
  for (let attempt = 0; attempt < 30; attempt++) {
    const balance = await client.readContract({
      address: wallet.baseSepolia.usdcAddress, abi: balanceOf,
      functionName: 'balanceOf', args: [account.address],
    });
    if (balance >= 12_000_000n) break;
    if (attempt === 29) throw new Error('Base Sepolia buyer funding was not confirmed');
    await setTimeout(2_000);
  }
  const challenge = await mppx.rawFetch(url, { headers: { accept: 'application/json' } });
  if (challenge.status !== 402 || !challenge.headers.get('payment-required')) throw new Error('Merchant did not offer x402');
  const credential = await mppx.createCredential(new Response(null, {
    status: 402,
    headers: { 'payment-required': challenge.headers.get('payment-required')! },
  }));
  const response = await mppx.rawFetch(url, {
    headers: { accept: 'application/json', 'payment-signature': credential },
  });
  if (!response.ok || !response.headers.get('payment-response') || !response.headers.get('payment-receipt')) {
    throw new Error(`Purchase failed: ${response.status}`);
  }
  console.log(JSON.stringify(await response.json()));
}
main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
