import { parseUnits, stringToHex, type Address, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { Actions, createClient, http } from "viem/tempo";
import { tempoLocalnet } from "viem/tempo/chains";

const rpcUrl = process.env.TEMPO_RPC_URL ?? "http://tempo-localnet:8545";
const token = (process.env.TEMPO_TOKEN ?? "0x20c0000000000000000000000000000000000001") as Address;
const payerPrivateKey = process.env.TEMPO_PAYER_PRIVATE_KEY as Hex;
const recipient = (process.env.TEMPO_RECIPIENT ?? "0x1111111111111111111111111111111111111111") as Address;
const amount = process.env.TEMPO_AMOUNT ?? "0.17";
const memo = process.env.TEMPO_MEMO ?? "TEMPO-EVAL-001";
const decimals = Number(process.env.TEMPO_DECIMALS ?? "6");

if (!payerPrivateKey) throw new Error("TEMPO_PAYER_PRIVATE_KEY is required");

const account = privateKeyToAccount(payerPrivateKey);
const client = createClient({
  account,
  chain: tempoLocalnet,
  feeToken: token,
  transport: http(rpcUrl),
});

const result = await Actions.token.transferSync(client, {
  amount: parseUnits(amount, decimals),
  memo: stringToHex(memo, { size: 32 }),
  to: recipient,
  token,
});
console.log(JSON.stringify({
  status: result.receipt.status,
  transactionHash: result.receipt.transactionHash,
}, null, 2));
