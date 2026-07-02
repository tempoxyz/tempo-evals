import { pad, parseAbi, parseUnits, stringToHex, type Address, type Hex } from "viem";
import { Account, Actions, createClient, http } from "viem/tempo";
import { tempoLocalnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const rpcUrl = required("TEMPO_RPC_URL");
const token = required("TEMPO_TOKEN") as Address;
const decimals = Number(required("TEMPO_DECIMALS"));
const amount = parseUnits(required("TEMPO_AMOUNT"), decimals);
const limit = parseUnits(required("TEMPO_ACCESS_KEY_LIMIT"), decimals);
const period = Number(required("TEMPO_ACCESS_KEY_PERIOD_SECONDS"));
const memo = pad(stringToHex(required("TEMPO_MEMO")), { size: 32 });
const tokenAbi = parseAbi([
  "function transferWithMemo(address to,uint256 amount,bytes32 memo) returns (bool)",
]);

const payer = Account.fromSecp256k1(required("TEMPO_PAYER_PRIVATE_KEY") as Hex);
const accessKey = Account.fromSecp256k1(required("TEMPO_ACCESS_KEY_PRIVATE_KEY") as Hex, {
  access: payer,
});

const payerClient = createClient({
  account: payer,
  chain: tempoLocalnet,
  feeToken: token,
  transport: http(rpcUrl),
});

await Actions.faucet.fundSync(payerClient, { account: payer.address });

const authorization = await Actions.accessKey.authorizeSync(payerClient, {
  accessKey,
  expiry: Math.floor(Date.now() / 1000) + period,
  limits: [{ token, limit, period }],
});

const accessKeyClient = createClient({
  account: accessKey,
  chain: tempoLocalnet,
  feeToken: token,
  transport: http(rpcUrl),
});

const hash = await accessKeyClient.writeContract({
  address: token,
  abi: tokenAbi,
  functionName: "transferWithMemo",
  args: [required("TEMPO_RECIPIENT") as Address, amount, memo],
});
const receipt = await accessKeyClient.waitForTransactionReceipt({ hash });

console.log(JSON.stringify({
  accessKey: authorization.publicKey,
  limit: limit.toString(),
  status: receipt.status,
  transactionHash: receipt.transactionHash,
}, null, 2));
