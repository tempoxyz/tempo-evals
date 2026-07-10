import { writeFileSync } from "node:fs";
import { parseUnits, type Address } from "viem";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";
import { Actions, createClient, http } from "viem/tempo";
import { tempoTestnet } from "viem/tempo/chains";

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

const taker = privateKeyToAccount(generatePrivateKey());
const client = (account: typeof taker) => createClient({
  account,
  chain: tempoTestnet,
  feeToken: tokenIn,
  transport: http(),
});
const takerClient = client(taker);

await Actions.faucet.fundSync(takerClient, { account: taker.address });
await Actions.token.approveSync(takerClient, {
  amount: amountIn,
  spender: dex,
  token: tokenIn,
});

const result = await Actions.dex.sellSync(takerClient, {
  amountIn,
  minAmountOut,
  tokenIn,
  tokenOut,
});

if (result.receipt.status !== "success") throw new Error("swap failed");

const output = {
  taker: { address: taker.address },
  swapTransactionHash: result.receipt.transactionHash,
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
