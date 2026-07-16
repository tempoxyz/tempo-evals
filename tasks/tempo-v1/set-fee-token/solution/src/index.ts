import { writeFileSync } from "node:fs";
import { type Address } from "viem";
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

const account = privateKeyToAccount(generatePrivateKey());
const feeToken = required("TEMPO_FEE_TOKEN") as Address;
const client = createClient({
  account,
  chain: tempoTestnet,
  transport,
});

await Actions.faucet.fundSync(client, { account: account.address, ...wait });
const result = await Actions.fee.setUserTokenSync(client, { token: feeToken, ...wait });
if (result.receipt.status !== "success") throw new Error("set fee token failed");

const output = {
  payer: { address: account.address },
  setFeeTokenTransactionHash: result.receipt.transactionHash,
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
