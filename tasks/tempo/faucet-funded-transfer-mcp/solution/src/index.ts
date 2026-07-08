import { parseUnits, type Address, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { Actions, createClient, http } from "viem/tempo";
import { tempoLocalnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const token = required("TEMPO_TOKEN") as Address;
const account = privateKeyToAccount(required("TEMPO_FAUCET_PRIVATE_KEY") as Hex);
const client = createClient({
  account,
  chain: tempoLocalnet,
  feeToken: token,
  transport: http(required("TEMPO_RPC_URL")),
});

await Actions.faucet.fundSync(client, { account: account.address });

const result = await Actions.token.transferSync(client, {
  amount: parseUnits(required("TEMPO_AMOUNT"), Number(required("TEMPO_DECIMALS"))),
  to: required("TEMPO_RECIPIENT") as Address,
  token,
});

console.log(JSON.stringify({ status: result.receipt.status, transactionHash: result.receipt.transactionHash }, null, 2));
