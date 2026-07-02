import { parseUnits, type Address, type Hex } from "viem";
import { Account, Actions, createClient, http } from "viem/tempo";
import { tempoLocalnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

function policyRef(value: string): "reject-all" | "allow-all" | bigint {
  if (value === "0") return "reject-all";
  if (value === "1") return "allow-all";
  return BigInt(value);
}

const rpcUrl = required("TEMPO_RPC_URL");
const token = required("TEMPO_TOKEN") as Address;
const decimals = Number(required("TEMPO_DECIMALS"));
const amount = parseUnits(required("TEMPO_AMOUNT"), decimals);

function clientFor(privateKey: Hex) {
  return createClient({
    account: Account.fromSecp256k1(privateKey),
    chain: tempoLocalnet,
    feeToken: token,
    transport: http(rpcUrl),
  });
}

const payerClient = clientFor(required("TEMPO_PAYER_PRIVATE_KEY") as Hex);
const recipientClient = clientFor(required("TEMPO_RECIPIENT_PRIVATE_KEY") as Hex);

await Actions.faucet.fundSync(payerClient, { account: payerClient.account.address });
await Actions.faucet.fundSync(recipientClient, { account: recipientClient.account.address });

const policyResult = await Actions.receivePolicy.setSync(recipientClient, {
  claimer: "self",
  senderPolicyId: policyRef(required("TEMPO_RECEIVE_POLICY_SENDER_POLICY_ID")),
  tokenPolicyId: policyRef(required("TEMPO_RECEIVE_POLICY_TOKEN_POLICY_ID")),
});

const transferResult = await Actions.token.transferSync(payerClient, {
  amount,
  memo: undefined,
  to: required("TEMPO_RECIPIENT") as Address,
  token,
});

console.log(JSON.stringify({
  policyStatus: policyResult.receipt.status,
  transferStatus: transferResult.receipt.status,
  transactionHash: transferResult.receipt.transactionHash,
}, null, 2));
