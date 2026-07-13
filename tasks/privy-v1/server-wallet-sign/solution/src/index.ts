import { writeFileSync } from "node:fs";
import { PrivyClient } from "@privy-io/node";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const message = required("PRIVY_MESSAGE");
const privy = new PrivyClient({
  appId: required("PRIVY_APP_ID"),
  appSecret: required("PRIVY_APP_SECRET"),
});

const wallet = await privy.wallets().create({ chain_type: "ethereum" });
const { signature } = await privy
  .wallets()
  .ethereum()
  .signMessage(wallet.id, { message });

const output = {
  wallet: { id: wallet.id, address: wallet.address },
  signature,
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
