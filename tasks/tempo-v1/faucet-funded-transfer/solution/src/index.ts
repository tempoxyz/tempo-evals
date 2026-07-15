import { writeFileSync } from "node:fs";
import { parseUnits, type Address } from "viem";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";
import { Actions, createClient, http } from "viem/tempo";
import { tempoTestnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const RECEIPT_TIMEOUT = 60_000;
const transport = http(undefined, { timeout: RECEIPT_TIMEOUT + 5_000 });
const wait = { timeout: RECEIPT_TIMEOUT };

const token = required("TEMPO_TOKEN") as Address;
const account = privateKeyToAccount(generatePrivateKey());
const client = createClient({
  account,
  chain: tempoTestnet,
  feeToken: token,
  transport,
});

const funding = await Actions.faucet.fundSync(client, { account: account.address, ...wait });

const result = await Actions.token.transferSync(client, {
  amount: parseUnits(required("TEMPO_AMOUNT"), Number(required("TEMPO_DECIMALS"))),
  to: required("TEMPO_RECIPIENT") as Address,
  token,
  ...wait,
});

if (result.receipt.status !== "success") throw new Error("transfer failed");

const output = {
  payer: { address: account.address },
  fundingTransactionHashes: funding.map((receipt) => receipt.transactionHash),
  transferTransactionHash: result.receipt.transactionHash,
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
