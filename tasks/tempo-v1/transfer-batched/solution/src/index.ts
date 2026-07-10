import { writeFileSync } from "node:fs";
import { createPublicClient, encodeFunctionData, parseUnits, type Address } from "viem";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";
import { Abis, Actions, createClient, http } from "viem/tempo";
import { tempoTestnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const token = required("TEMPO_TOKEN") as Address;
const recipientInput = required("TEMPO_RECIPIENTS");
const parsedRecipients: unknown = JSON.parse(recipientInput);
if (!Array.isArray(parsedRecipients) || !parsedRecipients.length || !parsedRecipients.every((value) => typeof value === "string")) {
  throw new Error("TEMPO_RECIPIENTS must be a non-empty JSON string array");
}
const recipients = parsedRecipients as Address[];
const transferAmount = parseUnits(required("TEMPO_AMOUNT"), Number(required("TEMPO_DECIMALS")));

const account = privateKeyToAccount(generatePrivateKey());
const client = createClient({ account, chain: tempoTestnet, feeToken: token, transport: http() });
const publicClient = createPublicClient({ chain: tempoTestnet, transport: http() });

await Actions.faucet.fundSync(client, { account: account.address });

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
if (receipt.status !== "success") throw new Error("batch transfer failed");

const output = {
  payer: { address: account.address },
  transferTransactionHash: transactionHash,
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
