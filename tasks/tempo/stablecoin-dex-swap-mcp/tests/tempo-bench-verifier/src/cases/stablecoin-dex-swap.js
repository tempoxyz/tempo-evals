// SYNCED FROM shared/tempo/verifier/src/cases/stablecoin-dex-swap.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, waitForEvidence } = require("../tempo");

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_STABLECOIN_DEX: config.stablecoinDex,
    TEMPO_DEX_MAKER_PRIVATE_KEY: config.dexMakerPrivateKey,
    TEMPO_SWAP_TOKEN_IN: config.swapTokenIn,
    TEMPO_SWAP_TOKEN_OUT: config.swapTokenOut,
    TEMPO_SWAP_AMOUNT_IN: config.swapAmountIn,
    TEMPO_SWAP_MIN_AMOUNT_OUT: config.swapMinAmountOut,
  };
}

function beforeLog(left, right) {
  return (
    left.blockNumber < right.blockNumber ||
    (left.blockNumber === right.blockNumber && left.logIndex < right.logIndex)
  );
}

async function verify({ client, config, fromBlock }) {
  const maker = privateKeyToAccount(config.dexMakerPrivateKey).address;
  const taker = privateKeyToAccount(config.payerPrivateKey).address;
  const expectedAmount = parseUnits(config.swapAmountIn, config.decimals);
  const event = parseAbiItem(
    "event OrderFilled(uint128 indexed orderId, address indexed maker, address indexed taker, uint128 amountFilled, bool partialFill)",
  );
  const orderPlaced = parseAbiItem(
    "event OrderPlaced(uint128 indexed orderId, address indexed maker, address indexed token, uint128 amount, bool isBid, int16 tick, bool isFlipOrder, int16 flipTick)",
  );

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const logs = await client.getLogs({
      address: config.stablecoinDex,
      event,
      args: { maker, taker },
      fromBlock,
      toBlock: latestBlock,
    });

    const match = logs.find((log) => log.args.amountFilled === expectedAmount);
    if (!match) return null;

    const orderLogs = await client.getLogs({
      address: config.stablecoinDex,
      event: orderPlaced,
      args: {
        orderId: match.args.orderId,
        maker,
        token: config.swapTokenOut,
      },
      fromBlock,
      toBlock: match.blockNumber,
    });
    const order = orderLogs.find(
      (log) => log.args.amount >= expectedAmount && !log.args.isBid && beforeLog(log, match),
    );

    return (
      order &&
      blockEvidence(match, {
        maker,
        orderId: match.args.orderId.toString(),
        orderPlacedTransactionHash: order.transactionHash,
        orderIsBid: order.args.isBid,
        orderToken: order.args.token,
        amountFilled: match.args.amountFilled.toString(),
      })
    );
  }, "no matching Stablecoin DEX OrderFilled event observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
