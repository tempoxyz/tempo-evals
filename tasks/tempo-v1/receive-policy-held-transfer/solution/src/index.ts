import { writeFileSync } from "node:fs";
import { parseUnits, type Address } from "viem";
import { generatePrivateKey } from "viem/accounts";
import { Account, Actions, createClient, http } from "viem/tempo";
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
const amount = parseUnits(required("TEMPO_AMOUNT"), Number(required("TEMPO_DECIMALS")));

const payer = Account.fromSecp256k1(generatePrivateKey());
const recipient = Account.fromSecp256k1(generatePrivateKey());
const clientConfig = {
  chain: tempoTestnet,
  feeToken: token,
  transport,
};
const payerClient = createClient({ ...clientConfig, account: payer });
const recipientClient = createClient({ ...clientConfig, account: recipient });

await Actions.faucet.fundSync(payerClient, { account: payer.address, ...wait });
await Actions.faucet.fundSync(recipientClient, { account: recipient.address, ...wait });

const policy = await Actions.receivePolicy.setSync(recipientClient, {
  senderPolicyId: "reject-all",
  tokenPolicyId: "allow-all",
  claimer: "self",
  ...wait,
});
if (policy.receipt.status !== "success") throw new Error("receive policy transaction failed");

const transfer = await Actions.token.transferSync(payerClient, {
  amount,
  to: recipient.address,
  token,
  ...wait,
});
if (transfer.receipt.status !== "success") throw new Error("transfer transaction failed");

const output = {
  payer: { address: payer.address },
  recipient: { address: recipient.address },
  policyTransactionHash: policy.receipt.transactionHash,
  transferTransactionHash: transfer.receipt.transactionHash,
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
