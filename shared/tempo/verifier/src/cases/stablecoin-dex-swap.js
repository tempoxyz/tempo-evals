// SYNCED FROM shared/tempo/verifier/src/cases/stablecoin-dex-swap.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, sameAddress, waitForEvidence } = require("../tempo");

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_STABLECOIN_DEX: config.stablecoinDex,
    TEMPO_SWAP_TOKEN_IN: config.swapTokenIn,
    TEMPO_SWAP_TOKEN_OUT: config.swapTokenOut,
    TEMPO_SWAP_AMOUNT_IN: config.swapAmountIn,
    TEMPO_SWAP_MIN_AMOUNT_OUT: config.swapMinAmountOut,
  };
}

async function verify({ client, config, fromBlock }) {
  // Liquidity is seeded at localnet startup by the maker account, so the
  // submission only has to take it: approve the DEX and swap.
  const maker = privateKeyToAccount(config.dexMakerPrivateKey).address;
  const taker = privateKeyToAccount(config.payerPrivateKey).address;
  const expectedAmount = parseUnits(config.swapAmountIn, config.decimals);
  const orderFilled = parseAbiItem(
    "event OrderFilled(uint128 indexed orderId, address indexed maker, address indexed taker, uint128 amountFilled, bool partialFill)",
  );
  const transfer = parseAbiItem(
    "event Transfer(address indexed from, address indexed to, uint256 value)",
  );

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const logs = await client.getLogs({
      address: config.stablecoinDex,
      event: orderFilled,
      args: { maker, taker },
      fromBlock,
      toBlock: latestBlock,
    });

    const match = logs.find((log) => log.args.amountFilled === expectedAmount);
    if (!match) return null;

    // Confirm the swap actually spent the configured input token by finding
    // the taker's token-in Transfer in the same transaction.
    const tokenInLogs = await client.getLogs({
      address: config.swapTokenIn,
      event: transfer,
      args: { from: taker },
      fromBlock: match.blockNumber,
      toBlock: match.blockNumber,
    });
    const spent = tokenInLogs.find((log) =>
      sameAddress(log.transactionHash, match.transactionHash),
    );
    if (!spent) return null;

    return blockEvidence(match, {
      maker,
      taker,
      orderId: match.args.orderId.toString(),
      amountFilled: match.args.amountFilled.toString(),
      tokenIn: config.swapTokenIn,
      tokenInAmount: spent.args.value.toString(),
    });
  }, "no matching Stablecoin DEX OrderFilled event observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
