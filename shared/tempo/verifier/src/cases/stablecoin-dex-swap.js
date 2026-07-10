const { parseAbiItem, parseUnits } = require("viem");
const { expectAddress, expectHash, expectObject, readResult } = require("../result");
const { defaultRuntimeEnv } = require("../submission");
const { findEvent, receiptAfter, sameAddress, waitForEvidence } = require("../tempo");

const ORDER_FILLED = parseAbiItem(
  "event OrderFilled(uint128 indexed orderId, address indexed maker, address indexed taker, uint128 amountFilled, bool partialFill)",
);
const TRANSFER = parseAbiItem("event Transfer(address indexed from, address indexed to, uint256 value)");

function result(config) {
  return readResult(config, (value) => {
    expectObject(config, value, ["taker", "swapTransactionHash"], "result");
    expectObject(config, value.taker, ["address"], "taker");
    return {
      taker: expectAddress(config, value.taker.address, "taker.address"),
      transactionHash: expectHash(config, value.swapTransactionHash, "swapTransactionHash"),
    };
  });
}

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
  const { taker, transactionHash } = result(config);
  const amount = parseUnits(config.swapAmountIn, config.decimals);

  return waitForEvidence(config, async () => {
    const receipt = await receiptAfter(
      client,
      fromBlock,
      transactionHash,
      taker,
      "reported swap transaction",
    );
    if (!receipt) return null;

    const fill = findEvent(receipt, config.stablecoinDex, ORDER_FILLED, (args) =>
      sameAddress(args.taker, taker),
    );
    if (!fill) throw new Error("reported transaction does not fill a DEX order");

    const spent = findEvent(receipt, config.swapTokenIn, TRANSFER, (args) =>
      sameAddress(args.from, taker) && args.value === amount,
    );
    if (!spent) throw new Error("reported transaction does not spend the requested swap input");

    const received = findEvent(receipt, config.swapTokenOut, TRANSFER, (args) =>
      sameAddress(args.from, config.stablecoinDex) && sameAddress(args.to, taker) && args.value > 0n,
    );
    if (!received) throw new Error("reported transaction does not receive the requested swap output");

    return {
      blockNumber: receipt.blockNumber.toString(),
      taker,
      orderId: fill.args.orderId.toString(),
      transactionHash,
    };
  }, "stablecoin DEX swap was not observed");
}

module.exports = { runtimeEnv, verify };
