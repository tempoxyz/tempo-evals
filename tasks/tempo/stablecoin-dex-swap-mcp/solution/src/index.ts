import { parseUnits, type Address, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { Actions, createClient, http } from "viem/tempo";
import { tempoLocalnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const tokenIn = required("TEMPO_SWAP_TOKEN_IN") as Address;
const tokenOut = required("TEMPO_SWAP_TOKEN_OUT") as Address;
const dex = required("TEMPO_STABLECOIN_DEX") as Address;
const decimals = Number(required("TEMPO_DECIMALS"));
const amountIn = parseUnits(required("TEMPO_SWAP_AMOUNT_IN"), decimals);
const minAmountOut = parseUnits(required("TEMPO_SWAP_MIN_AMOUNT_OUT"), decimals);

const client = createClient({
  account: privateKeyToAccount(required("TEMPO_PAYER_PRIVATE_KEY") as Hex),
  chain: tempoLocalnet,
  feeToken: tokenIn,
  transport: http(required("TEMPO_RPC_URL")),
});

await Actions.token.approveSync(client, {
  amount: amountIn,
  spender: dex,
  token: tokenIn,
});

const result = await Actions.dex.sellSync(client, {
  amountIn,
  minAmountOut,
  tokenIn,
  tokenOut,
});

console.log(JSON.stringify({
  status: result.receipt.status,
  transactionHash: result.receipt.transactionHash,
}, null, 2));
