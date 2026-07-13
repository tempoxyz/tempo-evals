import { writeFileSync } from "node:fs";
import { PrivyClient } from "@privy-io/node";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const privy = new PrivyClient({
  appId: required("PRIVY_APP_ID"),
  appSecret: required("PRIVY_APP_SECRET"),
});

const wallet = await privy.wallets().create({ chain_type: "ethereum" });

const output = {
  wallet: {
    id: wallet.id,
    address: wallet.address,
    chainType: wallet.chain_type,
  },
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
