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
const feeToken = required("TEMPO_TOKEN") as Address;
const salt = generatePrivateKey();
const suffix = salt.slice(2, 8).toUpperCase();
const name = `Stable Bench ${suffix}`;
const symbol = `TB${suffix.slice(0, 4)}`;
const client = createClient({
  account,
  chain: tempoTestnet,
  feeToken,
  transport,
});

await Actions.faucet.fundSync(client, { account: account.address, ...wait });
const tokenResult = await Actions.token.createSync(client, {
  admin: account.address,
  currency: required("TEMPO_STABLECOIN_CURRENCY"),
  name,
  salt,
  symbol,
  ...wait,
});

const policyResult = await Actions.policy.createSync(client, {
  addresses: [required("TEMPO_POLICY_ACCOUNT") as Address],
  admin: account.address,
  type: required("TEMPO_POLICY_TYPE") as "whitelist" | "blacklist",
  ...wait,
});

const linkResult = await Actions.token.changeTransferPolicySync(client, {
  policyId: policyResult.policyId,
  token: tokenResult.token,
  ...wait,
});

if (linkResult.receipt.status !== "success") throw new Error("link policy failed");

const output = {
  payer: { address: account.address },
  stablecoin: {
    address: tokenResult.token,
    name,
    symbol,
    salt,
  },
  policy: { id: policyResult.policyId.toString() },
  tokenCreateTransactionHash: tokenResult.receipt.transactionHash,
  policyCreateTransactionHash: policyResult.receipt.transactionHash,
  policyAccountTransactionHash: policyResult.receipt.transactionHash,
  linkPolicyTransactionHash: linkResult.receipt.transactionHash,
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
