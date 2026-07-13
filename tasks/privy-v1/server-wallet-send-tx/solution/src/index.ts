import { writeFileSync } from "node:fs";
import { PrivyClient } from "@privy-io/node";
import { createViemAccount } from "@privy-io/node/viem";
import { parseUnits, type Address } from "viem";
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
const decimals = Number(required("TEMPO_DECIMALS"));

const privy = new PrivyClient({
  appId: required("PRIVY_APP_ID"),
  appSecret: required("PRIVY_APP_SECRET"),
});

const wallet = await privy.wallets().create({ chain_type: "ethereum" });
const account = createViemAccount(privy, {
  walletId: wallet.id,
  address: wallet.address as Address,
});

const client = createClient({
  account,
  chain: tempoTestnet,
  feeToken: token,
  transport: http(),
});

await Actions.faucet.fundSync(client, { account: wallet.address as Address });

const result = await Actions.token.transferSync(client, {
  amount: parseUnits(amount, decimals),
  to: recipient,
  token,
});

if (result.receipt.status !== "success") throw new Error("transfer failed");

const output = {
  wallet: { id: wallet.id, address: wallet.address },
  transferTransactionHash: result.receipt.transactionHash,
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
