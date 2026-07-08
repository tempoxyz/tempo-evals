import { type Address, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { Actions, createClient, http } from "viem/tempo";
import { tempoLocalnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const account = privateKeyToAccount(required("TEMPO_PAYER_PRIVATE_KEY") as Hex);
const feeToken = required("TEMPO_TOKEN") as Address;
const client = createClient({
  account,
  chain: tempoLocalnet,
  feeToken,
  transport: http(required("TEMPO_RPC_URL")),
});

await Actions.faucet.fundSync(client, { account: account.address });

const tokenResult = await Actions.token.createSync(client, {
  admin: account.address,
  currency: required("TEMPO_STABLECOIN_CURRENCY"),
  name: required("TEMPO_STABLECOIN_NAME"),
  salt: required("TEMPO_STABLECOIN_SALT") as Hex,
  symbol: required("TEMPO_STABLECOIN_SYMBOL"),
});

const policyResult = await Actions.policy.createSync(client, {
  addresses: [required("TEMPO_POLICY_ACCOUNT") as Address],
  admin: account.address,
  type: required("TEMPO_POLICY_TYPE") as "whitelist" | "blacklist",
});

const linkResult = await Actions.token.changeTransferPolicySync(client, {
  policyId: policyResult.policyId,
  token: tokenResult.token,
});

console.log(JSON.stringify({
  linkStatus: linkResult.receipt.status,
  policyId: policyResult.policyId.toString(),
  token: tokenResult.token,
}, null, 2));
