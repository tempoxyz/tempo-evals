const { parseAbiItem } = require("viem");
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

async function verify({ client, config, fromBlock }) {
  const taker = privateKeyToAccount(config.payerPrivateKey).address;
  const event = parseAbiItem(
    "event OrderFilled(uint128 indexed orderId, address indexed maker, address indexed taker, uint128 amountFilled, bool partialFill)",
  );

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const logs = await client.getLogs({
      address: config.stablecoinDex,
      event,
      args: { taker },
      fromBlock,
      toBlock: latestBlock,
    });

    const match = logs[0];
    return match && blockEvidence(match, {
      orderId: match.args.orderId.toString(),
      amountFilled: match.args.amountFilled.toString(),
    });
  }, "no matching Stablecoin DEX OrderFilled event observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
