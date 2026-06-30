import { pad, parseUnits, stringToHex, type Address, type Hex } from "viem";
import { Account, Actions, createClient, http } from "viem/tempo";
import { tempoLocalnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const rpcUrl = required("TEMPO_RPC_URL");
const token = required("TEMPO_TOKEN") as Address;
const recipient = required("TEMPO_RECIPIENT") as Address;
const decimals = Number(required("TEMPO_DECIMALS"));
const amount = parseUnits(required("TEMPO_AMOUNT"), decimals);
const accessKeyLimit = parseUnits(required("TEMPO_ACCESS_KEY_LIMIT"), decimals);
const memo = pad(stringToHex(required("TEMPO_MEMO")), { size: 32 });

const payer = Account.fromSecp256k1(required("TEMPO_PAYER_PRIVATE_KEY") as Hex);
const accessKey = Account.fromSecp256k1(required("TEMPO_ACCESS_KEY_PRIVATE_KEY") as Hex, {
  access: payer,
});

const rootClient = createClient({
  account: payer,
  chain: tempoLocalnet,
  feeToken: token,
  transport: http(rpcUrl),
});

await Actions.accessKey.authorizeSync(rootClient, {
  accessKey,
  limits: [{ token, limit: accessKeyLimit }],
});

const accessKeyClient = createClient({
  account: accessKey,
  chain: tempoLocalnet,
  feeToken: token,
  transport: http(rpcUrl),
});

const result = await Actions.token.transferSync(accessKeyClient, {
  account: accessKey,
  amount,
  memo,
  to: recipient,
  token,
});

console.log(JSON.stringify({
  accessKey: accessKey.accessKeyAddress,
  status: result.receipt.status,
  transactionHash: result.receipt.transactionHash,
}, null, 2));
