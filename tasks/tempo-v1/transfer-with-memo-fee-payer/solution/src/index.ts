import { writeFileSync } from "node:fs";
import { parseUnits, stringToHex, type Address } from "viem";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";
import { Actions, createClient, http } from "viem/tempo";
import { tempoTestnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const token = required("TEMPO_TOKEN") as Address;
const feeToken = required("TEMPO_FEE_TOKEN") as Address;
const recipient = required("TEMPO_RECIPIENT") as Address;
const amount = parseUnits(required("TEMPO_AMOUNT"), Number(required("TEMPO_DECIMALS")));
const memo = stringToHex(required("TEMPO_MEMO"), { size: 32 });

const payer = privateKeyToAccount(generatePrivateKey());
const feePayer = privateKeyToAccount(generatePrivateKey());
const client = createClient({
  account: payer,
  chain: tempoTestnet,
  feeToken,
  transport: http(),
});

await Actions.faucet.fundSync(client, { account: payer.address });
await Actions.faucet.fundSync(client, { account: feePayer.address });

const result = await Actions.token.transferSync(client, {
  amount,
  feePayer,
  feeToken,
  memo,
  to: recipient,
  token,
});

if (result.receipt.status !== "success") throw new Error("transfer failed");

const output = {
  payer: { address: payer.address },
  feePayer: { address: feePayer.address },
  transferTransactionHash: result.receipt.transactionHash,
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
