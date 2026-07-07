const { erc20Abi, getAbiItem, parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, sameAddress, waitForEvidence } = require("../tempo");

const approvalEvent = getAbiItem({ abi: erc20Abi, name: "Approval" });
const transferEvent = getAbiItem({ abi: erc20Abi, name: "Transfer" });
const orderPlacedEvent = parseAbiItem(
  "event OrderPlaced(uint128 indexed orderId, address indexed maker, address indexed token, uint128 amount, bool isBid, int16 tick, bool isFlipOrder, int16 flipTick)",
);
const orderFilledEvent = parseAbiItem(
  "event OrderFilled(uint128 indexed orderId, address indexed maker, address indexed taker, uint128 amountFilled, bool partialFill)",
);

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

async function verify({ client, config, fromBlock }) {
  const taker = privateKeyToAccount(config.payerPrivateKey).address;
  const maker = privateKeyToAccount(config.dexMakerPrivateKey).address;
  const amountIn = parseUnits(config.swapAmountIn, config.decimals);
  const minAmountOut = parseUnits(config.swapMinAmountOut, config.decimals);

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const fillLogs = await client.getLogs({
      address: config.stablecoinDex,
      event: orderFilledEvent,
      args: { maker, taker },
      fromBlock,
      toBlock: latestBlock,
    });

    for (const fillLog of fillLogs) {
      const [orderLog] = await client.getLogs({
        address: config.stablecoinDex,
        event: orderPlacedEvent,
        args: { orderId: fillLog.args.orderId, maker, token: config.swapTokenOut },
        fromBlock,
        toBlock: latestBlock,
      });
      if (!orderLog || orderLog.args.isBid || orderLog.args.amount < fillLog.args.amountFilled) {
        continue;
      }

      const [takerApprovals, makerApprovals, inputTransfers, outputTransfers] = await Promise.all([
        client.getLogs({
          address: config.swapTokenIn,
          event: approvalEvent,
          args: { owner: taker, spender: config.stablecoinDex },
          fromBlock,
          toBlock: latestBlock,
        }),
        client.getLogs({
          address: config.swapTokenOut,
          event: approvalEvent,
          args: { owner: maker, spender: config.stablecoinDex },
          fromBlock,
          toBlock: latestBlock,
        }),
        client.getLogs({
          address: config.swapTokenIn,
          event: transferEvent,
          args: { from: taker, to: config.stablecoinDex },
          fromBlock,
          toBlock: latestBlock,
        }),
        client.getLogs({
          address: config.swapTokenOut,
          event: transferEvent,
          args: { from: config.stablecoinDex, to: taker },
          fromBlock,
          toBlock: latestBlock,
        }),
      ]);

      const sameTx = (log) => sameAddress(log.transactionHash, fillLog.transactionHash);
      if (
        fillLog.args.amountFilled < minAmountOut ||
        !takerApprovals.some((log) => log.args.value >= amountIn) ||
        !makerApprovals.some((log) => log.args.value >= orderLog.args.amount) ||
        !inputTransfers.some((log) => sameTx(log) && log.args.value === amountIn) ||
        !outputTransfers.some((log) => sameTx(log) && log.args.value === fillLog.args.amountFilled)
      ) {
        continue;
      }

      return blockEvidence(fillLog, {
        orderId: fillLog.args.orderId.toString(),
        maker,
        tokenIn: config.swapTokenIn,
        tokenOut: config.swapTokenOut,
        amountIn: amountIn.toString(),
        minAmountOut: minAmountOut.toString(),
        amountFilled: fillLog.args.amountFilled.toString(),
      });
    }

    return null;
  }, "no matching Stablecoin DEX swap, liquidity order, and approvals observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
