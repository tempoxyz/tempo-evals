const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, sameAddress, waitForEvidence } = require("../tempo");

const approvalEvent = parseAbiItem(
  "event Approval(address indexed owner, address indexed spender, uint256 value)",
);
const transferEvent = parseAbiItem("event Transfer(address indexed from, address indexed to, uint256 value)");
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

function hasApproval(logs, minimumValue) {
  return logs.some((log) => log.args.value >= minimumValue);
}

function sameTransaction(log, transactionHash) {
  return log.transactionHash.toLowerCase() === transactionHash.toLowerCase();
}

async function verify({ client, config, fromBlock }) {
  const taker = privateKeyToAccount(config.payerPrivateKey).address;
  const maker = privateKeyToAccount(config.dexMakerPrivateKey).address;
  const expectedAmountIn = parseUnits(config.swapAmountIn, config.decimals);
  const expectedMinAmountOut = parseUnits(config.swapMinAmountOut, config.decimals);

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const fillLogs = await client.getLogs({
      address: config.stablecoinDex,
      event: orderFilledEvent,
      args: { taker },
      fromBlock,
      toBlock: latestBlock,
    });

    for (const fillLog of fillLogs) {
      if (!sameAddress(fillLog.args.maker, maker)) continue;

      const [orderLog] = await client.getLogs({
        address: config.stablecoinDex,
        event: orderPlacedEvent,
        args: {
          orderId: fillLog.args.orderId,
          maker,
          token: config.swapTokenOut,
        },
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

      const inputTransfer = inputTransfers.find(
        (log) => sameTransaction(log, fillLog.transactionHash) && log.args.value === expectedAmountIn,
      );
      const outputTransfer = outputTransfers.find(
        (log) =>
          sameTransaction(log, fillLog.transactionHash) &&
          log.args.value === fillLog.args.amountFilled &&
          log.args.value >= expectedMinAmountOut,
      );
      if (
        !inputTransfer ||
        !outputTransfer ||
        !hasApproval(takerApprovals, expectedAmountIn) ||
        !hasApproval(makerApprovals, orderLog.args.amount)
      ) {
        continue;
      }

      return blockEvidence(fillLog, {
        orderId: fillLog.args.orderId.toString(),
        amountIn: expectedAmountIn.toString(),
        minAmountOut: expectedMinAmountOut.toString(),
        amountFilled: fillLog.args.amountFilled.toString(),
        maker,
        makerOrderAmount: orderLog.args.amount.toString(),
        tokenIn: config.swapTokenIn,
        tokenOut: config.swapTokenOut,
      });
    }

    return null;
  }, "no matching Stablecoin DEX swap, liquidity order, and approvals observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
