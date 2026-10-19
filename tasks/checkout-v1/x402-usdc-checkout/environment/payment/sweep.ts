import { randomBytes } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { bytesToHex, createPublicClient, createWalletClient, http, parseSignature } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
import { baseSepolia } from 'viem/chains';

const sourceKey = process.env.X402_FUNDING_PRIVATE_KEY as `0x${string}`;
if (!/^0x[0-9a-fA-F]{64}$/.test(sourceKey || '')) throw new Error('X402_FUNDING_PRIVATE_KEY is required');
const source = privateKeyToAccount(sourceKey);
if (source.address.toLowerCase() !== process.env.X402_RECIPIENT_ADDRESS?.toLowerCase()) {
  throw new Error('The x402 recipient must be the funding wallet');
}
const wallet = JSON.parse(readFileSync(process.env.WALLET_PATH || '/wallet/wallet.json', 'utf8'));
if (!wallet.baseSepolia?.privateKey) {
  console.log('No Base Sepolia buyer was funded');
  process.exit(0);
}
const buyer = privateKeyToAccount(wallet.baseSepolia.privateKey);
const usdc = '0x036CbD53842c5426634e7929541eC2318f3dCF7e';
const abi = [{
  type: 'function', name: 'balanceOf', stateMutability: 'view',
  inputs: [{ name: 'account', type: 'address' }], outputs: [{ type: 'uint256' }],
}, {
  type: 'function', name: 'transferWithAuthorization', stateMutability: 'nonpayable',
  inputs: [
    { name: 'from', type: 'address' }, { name: 'to', type: 'address' },
    { name: 'value', type: 'uint256' }, { name: 'validAfter', type: 'uint256' },
    { name: 'validBefore', type: 'uint256' }, { name: 'nonce', type: 'bytes32' },
    { name: 'v', type: 'uint8' }, { name: 'r', type: 'bytes32' }, { name: 's', type: 'bytes32' },
  ], outputs: [],
}] as const;
const transport = http(process.env.BASE_SEPOLIA_RPC_URL || 'https://sepolia.base.org');
const publicClient = createPublicClient({ chain: baseSepolia, transport });
const balance = await publicClient.readContract({ address: usdc, abi, functionName: 'balanceOf', args: [buyer.address] });
if (balance === 0n) {
  console.log('No unspent buyer USDC to recover');
  process.exit(0);
}
const validAfter = 0n;
const validBefore = BigInt(Math.floor(Date.now() / 1000) + 600);
const nonce = bytesToHex(randomBytes(32));
const signature = await buyer.signTypedData({
  domain: { name: 'USDC', version: '2', chainId: 84532, verifyingContract: usdc },
  types: { TransferWithAuthorization: [
    { name: 'from', type: 'address' }, { name: 'to', type: 'address' },
    { name: 'value', type: 'uint256' }, { name: 'validAfter', type: 'uint256' },
    { name: 'validBefore', type: 'uint256' }, { name: 'nonce', type: 'bytes32' },
  ] },
  primaryType: 'TransferWithAuthorization',
  message: {
    from: buyer.address, to: source.address, value: balance,
    validAfter, validBefore, nonce,
  },
});
const { v, r, s } = parseSignature(signature);
if (v === undefined) throw new Error('Buyer authorization signature has no recovery bit');
const client = createWalletClient({ account: source, chain: baseSepolia, transport });
const hash = await client.writeContract({
  address: usdc, abi, functionName: 'transferWithAuthorization',
  args: [buyer.address, source.address, balance, validAfter, validBefore, nonce, Number(v), r, s],
});
const receipt = await publicClient.waitForTransactionReceipt({ hash, timeout: 90_000 });
if (receipt.status !== 'success') throw new Error('Buyer USDC recovery failed');
console.log(`Recovered ${balance} Base Sepolia USDC units from trial buyer`);
