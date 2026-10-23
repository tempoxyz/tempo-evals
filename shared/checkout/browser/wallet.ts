// Trial-only injected wallet. Keys stay in this trusted Node process, never pages.
import { readFileSync } from 'node:fs';
import { createWalletClient, http } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';
import { Chain } from 'viem/tempo';
import type { BrowserContext } from 'playwright-core';

const installed = new WeakMap<BrowserContext, Promise<void>>();
export function installWallet(context: BrowserContext) {
  let pending = installed.get(context);
  if (!pending) {
    pending = configureWallet(context);
    installed.set(context, pending);
  }
  return pending;
}
async function configureWallet(context: BrowserContext) {
  const { tempo } = JSON.parse(readFileSync('/wallet/wallet.json', 'utf8'));
  if (tempo.chainId !== 42431) throw new Error('Checkout wallet requires Tempo testnet');
  const account = privateKeyToAccount(tempo.privateKey);
  const client = createWalletClient({ account, chain: Chain.testnet, transport: http(tempo.rpcUrl) });
  if (await client.getChainId() !== 42431) throw new Error('Checkout wallet RPC is not Tempo testnet');
  await context.exposeBinding('__tempoWalletRequest', async (_source, { method, params = [] }) => {
    switch (method) {
      case 'eth_accounts': case 'eth_requestAccounts': return [account.address];
      case 'eth_chainId': return '0xa5bf';
      case 'net_version': return '42431';
      case 'wallet_switchEthereumChain': case 'wallet_addEthereumChain':
        if (Number(params[0]?.chainId) !== 42431) throw new Error('Only Tempo testnet is available');
        return null;
      case 'personal_sign': {
        if (params[1]?.toLowerCase() !== account.address.toLowerCase()) throw new Error('Unknown signer');
        return account.signMessage({ message: { raw: params[0] } });
      }
      case 'eth_signTypedData_v4': {
        if (params[0]?.toLowerCase() !== account.address.toLowerCase()) throw new Error('Unknown signer');
        const data = JSON.parse(params[1]);
        if (data.domain?.chainId !== undefined && Number(data.domain.chainId) !== 42431) throw new Error('Wrong signing chain');
        return account.signTypedData(data);
      }
      case 'eth_sendTransaction': {
        const tx = params[0];
        if (tx.from?.toLowerCase() !== account.address.toLowerCase()) throw new Error('Unknown sender');
        return client.sendTransaction({
          to: tx.to, data: tx.data,
          ...(tx.value ? { value: BigInt(tx.value) } : {}),
          ...(tx.gas ? { gas: BigInt(tx.gas) } : {}),
        });
      }
      default:
        if (!['eth_call', 'eth_getBalance', 'eth_getTransactionReceipt', 'eth_getTransactionByHash', 'eth_blockNumber', 'eth_estimateGas', 'eth_gasPrice', 'eth_getCode'].includes(method)) throw new Error('Unsupported wallet method');
        return client.request({ method, params });
    }
  });
  await context.addInitScript({ content: readFileSync(new URL('./wallet-provider.js', import.meta.url), 'utf8').replace('__ADDRESS__', JSON.stringify(account.address)) });
}
