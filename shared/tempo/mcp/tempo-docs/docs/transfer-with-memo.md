# Tempo TIP-20 Transfer With Memo

Use a TIP-20 token contract's `transferWithMemo` function when a payment needs
an onchain memo that another system can reconcile later.

## Inputs

Read task-provided values from environment variables:

- `TEMPO_RPC_URL`: Tempo localnet JSON-RPC URL.
- `TEMPO_PAYER_PRIVATE_KEY`: private key for the funded payer account.
- `TEMPO_TOKEN`: TIP-20 token contract address.
- `TEMPO_RECIPIENT`: recipient account address.
- `TEMPO_AMOUNT`: human-readable token amount.
- `TEMPO_DECIMALS`: token decimals for `parseUnits`.
- `TEMPO_MEMO`: memo text to attach to the payment.

## TypeScript Pattern

```ts
import {
  createPublicClient,
  createWalletClient,
  defineChain,
  http,
  pad,
  parseAbi,
  parseUnits,
  stringToHex,
  type Address,
  type Hex,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";

const rpcUrl = process.env.TEMPO_RPC_URL!;
const token = process.env.TEMPO_TOKEN! as Address;
const privateKey = process.env.TEMPO_PAYER_PRIVATE_KEY! as Hex;
const recipient = process.env.TEMPO_RECIPIENT! as Address;
const amount = process.env.TEMPO_AMOUNT!;
const decimals = Number(process.env.TEMPO_DECIMALS!);
const memo = process.env.TEMPO_MEMO!;

const abi = parseAbi([
  "function transferWithMemo(address to,uint256 amount,bytes32 memo) returns (bool)",
]);

const publicClient = createPublicClient({ transport: http(rpcUrl) });
const chainIdHex = await publicClient.request({ method: "eth_chainId" });
const chain = defineChain({
  id: Number(BigInt(chainIdHex as Hex)),
  name: "Tempo Localnet",
  nativeCurrency: { name: "Tempo", symbol: "TEMPO", decimals: 18 },
  rpcUrls: { default: { http: [rpcUrl] } },
});

const account = privateKeyToAccount(privateKey);
const walletClient = createWalletClient({
  account,
  chain,
  transport: http(rpcUrl),
});

const hash = await walletClient.writeContract({
  address: token,
  abi,
  functionName: "transferWithMemo",
  args: [
    recipient,
    parseUnits(amount, decimals),
    pad(stringToHex(memo), { size: 32 }),
  ],
});

await publicClient.waitForTransactionReceipt({ hash });
```

## Common Mistakes

- Do not call plain `transfer`; the verifier expects the memo event.
- Convert the amount with `parseUnits(amount, decimals)`.
- Encode the memo as `bytes32`, for example with
  `pad(stringToHex(memo), { size: 32 })`.
- Wait for the transaction receipt before exiting so the grader can observe the
  onchain event.
