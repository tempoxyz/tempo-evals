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
const recipient = required("TEMPO_RECIPIENT") as Address;
const amount = required("TEMPO_AMOUNT");
const memo = required("TEMPO_MEMO");
const decimals = Number(required("TEMPO_DECIMALS"));

const account = privateKeyToAccount(generatePrivateKey());
const client = createClient({
  account,
  chain: tempoTestnet,
  feeToken: token,
  transport: http(),
});

await Actions.faucet.fundSync(client, { account: account.address });

const result = await Actions.token.transferSync(client, {
  amount: parseUnits(amount, decimals),
  memo: stringToHex(memo, { size: 32 }),
  to: recipient,
  token,
});

if (result.receipt.status !== "success") throw new Error("transfer failed");

const output = {
  payer: { address: account.address },
  transferTransactionHash: result.receipt.transactionHash,
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
