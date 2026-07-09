import { parseUnits, stringToHex, type Address, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { Actions, createClient, http } from "viem/tempo";
import { tempoLocalnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const rpcUrl = required("TEMPO_RPC_URL");
const token = required("TEMPO_TOKEN") as Address;
const feeToken = required("TEMPO_FEE_TOKEN") as Address;
const recipient = required("TEMPO_RECIPIENT") as Address;
const amount = parseUnits(required("TEMPO_AMOUNT"), Number(required("TEMPO_DECIMALS")));
const memo = stringToHex(required("TEMPO_MEMO"), { size: 32 });

const payer = privateKeyToAccount(required("TEMPO_PAYER_PRIVATE_KEY") as Hex);
const feePayer = privateKeyToAccount(required("TEMPO_FEE_PAYER_PRIVATE_KEY") as Hex);
const client = createClient({
  account: payer,
  chain: tempoLocalnet,
  feeToken,
  transport: http(rpcUrl),
});

// The fee payer sponsors the transfer, so it needs fee-token balance.
await Actions.faucet.fundSync(client, { account: feePayer.address });

const result = await Actions.token.transferSync(client, {
  amount,
  feePayer,
  feeToken,
  memo,
  to: recipient,
  token,
});

console.log(JSON.stringify({ status: result.receipt.status, transactionHash: result.receipt.transactionHash }, null, 2));
