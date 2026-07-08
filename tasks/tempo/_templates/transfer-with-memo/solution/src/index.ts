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

const rpcUrl = process.env.TEMPO_RPC_URL ?? "http://tempo-localnet:8545";
const token = (process.env.TEMPO_TOKEN ?? "0x20c0000000000000000000000000000000000001") as Address;
const payerPrivateKey = process.env.TEMPO_PAYER_PRIVATE_KEY as Hex;
const recipient = (process.env.TEMPO_RECIPIENT ?? "0x1111111111111111111111111111111111111111") as Address;
const amount = process.env.TEMPO_AMOUNT ?? "0.17";
const memo = process.env.TEMPO_MEMO ?? "TEMPO-EVAL-001";
const decimals = Number(process.env.TEMPO_DECIMALS ?? "6");

if (!payerPrivateKey) {
  throw new Error("TEMPO_PAYER_PRIVATE_KEY is required");
}

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

const account = privateKeyToAccount(payerPrivateKey);
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

const receipt = await publicClient.waitForTransactionReceipt({ hash });
console.log(JSON.stringify({ hash, status: receipt.status }, null, 2));
