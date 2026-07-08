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
const client = createClient({
  account,
  chain: tempoLocalnet,
  feeToken,
  transport: http(required("TEMPO_RPC_URL")),
});

await Actions.faucet.fundSync(client, { account: account.address });

const transactionHash = await Actions.fee.setUserToken(client, { token: feeToken });
const receipt = await client.waitForTransactionReceipt({ hash: transactionHash });
const userToken = await Actions.fee.getUserToken(client);
console.log(JSON.stringify({ status: receipt.status, token: userToken?.address, transactionHash }, null, 2));
