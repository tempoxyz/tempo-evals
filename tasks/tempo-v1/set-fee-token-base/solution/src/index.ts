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
const feeToken = required("TEMPO_FEE_TOKEN") as Address;
// No client-level feeToken: the transaction pays gas with the account's
// current fee token preference while setting the new default.
const client = createClient({
  account,
  chain: tempoLocalnet,
  transport: http(required("TEMPO_RPC_URL")),
});

const result = await Actions.fee.setUserTokenSync(client, { token: feeToken });
console.log(JSON.stringify({
  status: result.receipt.status,
  token: result.token,
  transactionHash: result.receipt.transactionHash,
}, null, 2));
