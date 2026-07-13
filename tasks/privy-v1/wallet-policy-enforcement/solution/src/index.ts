import { writeFileSync } from "node:fs";
import { PrivyClient } from "@privy-io/node";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const allowedRecipient = required("PRIVY_ALLOWED_RECIPIENT");

const privy = new PrivyClient({
  appId: required("PRIVY_APP_ID"),
  appSecret: required("PRIVY_APP_SECRET"),
});

const policy = await privy.policies().create({
  chain_type: "ethereum",
  name: "Recipient allowlist",
  version: "1.0",
  rules: [
    {
      name: "Allow signing to the allowed recipient",
      method: "eth_signTransaction",
      action: "ALLOW",
      conditions: [
        {
          field_source: "ethereum_transaction",
          field: "to",
          operator: "eq",
          value: allowedRecipient,
        },
      ],
    },
    {
      name: "Allow sending to the allowed recipient",
      method: "eth_sendTransaction",
      action: "ALLOW",
      conditions: [
        {
          field_source: "ethereum_transaction",
          field: "to",
          operator: "eq",
          value: allowedRecipient,
        },
      ],
    },
  ],
});

const wallet = await privy.wallets().create({
  chain_type: "ethereum",
  policy_ids: [policy.id],
});

const signed = await privy.wallets().ethereum().signTransaction(wallet.id, {
  params: {
    transaction: {
      to: allowedRecipient,
      value: "0x1",
      chain_id: 42431,
      type: 2,
      nonce: 0,
      gas_limit: "0x5208",
      max_fee_per_gas: "0x3b9aca00",
      max_priority_fee_per_gas: "0x3b9aca00",
    },
  },
});

const output = {
  wallet: { id: wallet.id, address: wallet.address },
  policyId: policy.id,
  signedTransaction: signed.signed_transaction,
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
