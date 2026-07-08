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
import { writeFile } from "node:fs/promises";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const rpcUrl = required("TEMPO_RPC_URL");
const token = required("TEMPO_TOKEN") as Address;
const payerPrivateKey = required("TEMPO_PAYER_PRIVATE_KEY") as Hex;
const recipient = required("TEMPO_RECIPIENT") as Address;
const amount = required("TEMPO_AMOUNT");
const memo = required("TEMPO_MEMO");
const decimals = Number(required("TEMPO_DECIMALS"));

const abi = parseAbi([
  "function transferWithMemo(address to,uint256 amount,bytes32 memo) returns (bool)",
]);

const publicClient = createPublicClient({ transport: http(rpcUrl) });
const chainIdHex = await publicClient.request({ method: "eth_chainId" });
const chain = defineChain({
  id: Number(BigInt(chainIdHex as Hex)),
  name: "Tempo Testnet",
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

await writeFile(
  "/app/out.json",
  `${JSON.stringify({ transactionHash: hash }, null, 2)}\n`,
);
console.log(JSON.stringify({ transactionHash: hash }, null, 2));
