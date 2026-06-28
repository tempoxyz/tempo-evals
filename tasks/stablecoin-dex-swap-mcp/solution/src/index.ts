import { parseUnits, type Address, type Hex } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { Actions, createClient, http } from "viem/tempo";
import { tempoLocalnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

function tempoClient(privateKey: Hex, feeToken: Address) {
  return createClient({
    account: privateKeyToAccount(privateKey),
    chain: tempoLocalnet,
    feeToken,
    transport: http(required("TEMPO_RPC_URL")),
  });
}

const tokenIn = required("TEMPO_SWAP_TOKEN_IN") as Address;
const tokenOut = required("TEMPO_SWAP_TOKEN_OUT") as Address;
const dex = required("TEMPO_STABLECOIN_DEX") as Address;
const decimals = Number(required("TEMPO_DECIMALS"));
const amountIn = parseUnits(required("TEMPO_SWAP_AMOUNT_IN"), decimals);
const minAmountOut = parseUnits(required("TEMPO_SWAP_MIN_AMOUNT_OUT"), decimals);

const takerClient = tempoClient(required("TEMPO_PAYER_PRIVATE_KEY") as Hex, tokenIn);
const makerClient = tempoClient(required("TEMPO_DEX_MAKER_PRIVATE_KEY") as Hex, tokenIn);

await Actions.faucet.fundSync(takerClient, { account: takerClient.account.address });
await Actions.faucet.fundSync(makerClient, { account: makerClient.account.address });

await Actions.dex.createPairSync(makerClient, { base: tokenOut }).catch(() => undefined);

const makerAmount = amountIn * 2n;
await Actions.token.approveSync(makerClient, {
  amount: makerAmount,
  spender: dex,
  token: tokenOut,
});
await Actions.dex.placeSync(makerClient, {
  amount: makerAmount,
  tick: 0,
  token: tokenOut,
  type: "sell",
});

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

console.log(JSON.stringify({ status: result.receipt.status, transactionHash: result.receipt.transactionHash }, null, 2));
