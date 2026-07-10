import { createPublicClient, encodeFunctionData, parseUnits, type Address, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { Abis, createClient, http } from "viem/tempo";
import { tempoLocalnet } from "viem/tempo/chains";

const rpcUrl = process.env.TEMPO_RPC_URL ?? "http://tempo-localnet:8545";
const token = (process.env.TEMPO_TOKEN ?? "0x20c0000000000000000000000000000000000001") as Address;
const payerPrivateKey = process.env.TEMPO_PAYER_PRIVATE_KEY as Hex;
const amount = process.env.TEMPO_AMOUNT ?? "0.01";
const decimals = Number(process.env.TEMPO_DECIMALS ?? "6");

if (!payerPrivateKey) throw new Error("TEMPO_PAYER_PRIVATE_KEY is required");

const recipientInput = process.env.TEMPO_RECIPIENTS;
if (!recipientInput) throw new Error("TEMPO_RECIPIENTS is required");

const parsedRecipients: unknown = JSON.parse(recipientInput);
if (!Array.isArray(parsedRecipients) || parsedRecipients.length === 0 || !parsedRecipients.every((value) => typeof value === "string")) {
  throw new Error("TEMPO_RECIPIENTS must be a non-empty JSON string array");
}
const recipients = parsedRecipients as Address[];
const transferAmount = parseUnits(amount, decimals);

const account = privateKeyToAccount(payerPrivateKey);
const client = createClient({
  account,
  chain: tempoLocalnet,
  feeToken: token,
  transport: http(rpcUrl),
});
const publicClient = createPublicClient({
  chain: tempoLocalnet,
  transport: http(rpcUrl),
});

const calls = recipients.map((to) => ({
  to: token,
  data: encodeFunctionData({
    abi: Abis.tip20,
    functionName: "transfer",
    args: [to, transferAmount],
  }),
}));
const transactionHash = await client.sendTransaction({ calls });
const receipt = await publicClient.waitForTransactionReceipt({ hash: transactionHash });

console.log(JSON.stringify({
  recipientCount: recipients.length,
  status: receipt.status,
  transactionHash,
}, null, 2));
