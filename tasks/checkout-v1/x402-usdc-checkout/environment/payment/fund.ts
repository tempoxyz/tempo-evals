import { chmodSync, readFileSync, writeFileSync } from 'node:fs';
import { createPublicClient, createWalletClient, http } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
import { baseSepolia } from 'viem/chains';

const sourceKey = process.env.X402_FUNDING_PRIVATE_KEY as `0x${string}`;
if (!/^0x[0-9a-fA-F]{64}$/.test(sourceKey || '')) throw new Error('X402_FUNDING_PRIVATE_KEY is required');
const source = privateKeyToAccount(sourceKey);
const recipient = process.env.X402_RECIPIENT_ADDRESS;
if (source.address.toLowerCase() !== recipient?.toLowerCase()) throw new Error('The x402 recipient must be the funding wallet');
const rpcUrl = process.env.BASE_SEPOLIA_RPC_URL || 'https://sepolia.base.org';
const usdc = '0x036CbD53842c5426634e7929541eC2318f3dCF7e';
const amount = 12_000_000n;
const abi = [{
  type: 'function', name: 'balanceOf', stateMutability: 'view',
  inputs: [{ name: 'account', type: 'address' }], outputs: [{ type: 'uint256' }],
}, {
  type: 'function', name: 'transfer', stateMutability: 'nonpayable',
  inputs: [{ name: 'to', type: 'address' }, { name: 'value', type: 'uint256' }], outputs: [{ type: 'bool' }],
}] as const;
const publicClient = createPublicClient({ chain: baseSepolia, transport: http(rpcUrl) });
const walletClient = createWalletClient({ account: source, chain: baseSepolia, transport: http(rpcUrl) });
const walletPath = '/wallet/wallet.json';
const wallet = JSON.parse(readFileSync(walletPath, 'utf8'));
const buyer = wallet.tempo.address as `0x${string}`;
const sourceBalance = await publicClient.readContract({ address: usdc, abi, functionName: 'balanceOf', args: [source.address] });
if (sourceBalance < amount) throw new Error('The x402 funding wallet needs at least 12 Base Sepolia test USDC');
if (await publicClient.getBalance({ address: source.address }) === 0n) throw new Error('The x402 funding wallet needs Base Sepolia test ETH for gas');
wallet.baseSepolia = {
  chainId: 84532,
  rpcUrl: 'https://sepolia.base.org',
  usdcAddress: usdc,
  address: buyer,
  privateKey: wallet.tempo.privateKey,
};
chmodSync(walletPath, 0o600);
writeFileSync(walletPath, JSON.stringify(wallet, null, 2) + '\n');
chmodSync(walletPath, 0o444);
const hash = await walletClient.writeContract({ address: usdc, abi, functionName: 'transfer', args: [buyer, amount] });
try {
  const receipt = await publicClient.waitForTransactionReceipt({ hash, timeout: 60_000 });
  if (receipt.status !== 'success') throw new Error('Funding transfer failed');
} catch (error) {
  if (error instanceof Error && error.message === 'Funding transfer failed') throw error;
  console.warn(`Funding transfer ${hash} was submitted; receipt lookup is pending`);
}
console.log('Isolated Base Sepolia buyer funded and ready');
