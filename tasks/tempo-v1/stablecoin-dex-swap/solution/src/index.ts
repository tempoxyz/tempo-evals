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

const RECEIPT_TIMEOUT = 60_000;
const transport = http(undefined, { timeout: RECEIPT_TIMEOUT + 5_000 });
const wait = { timeout: RECEIPT_TIMEOUT };

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
  transport,
});
const takerClient = client(taker);

await Actions.faucet.fundSync(takerClient, { account: taker.address, ...wait });
await Actions.token.approveSync(takerClient, {
  amount: amountIn,
  spender: dex,
  token: tokenIn,
  ...wait,
});

const result = await Actions.dex.sellSync(takerClient, {
  amountIn,
  minAmountOut,
  tokenIn,
  tokenOut,
  ...wait,
});

if (result.receipt.status !== "success") throw new Error("swap failed");

const output = {
  taker: { address: taker.address },
  swapTransactionHash: result.receipt.transactionHash,
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
