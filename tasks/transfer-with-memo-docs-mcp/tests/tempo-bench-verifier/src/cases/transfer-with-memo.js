const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { memoEncodings, sleep } = require("../tempo");

async function verify({ client, config, fromBlock }) {
  const payer = privateKeyToAccount(config.payerPrivateKey).address;
  const expectedValue = parseUnits(config.amount, config.decimals);
  const event = parseAbiItem(
    "event TransferWithMemo(address indexed from, address indexed to, uint256 value, bytes32 indexed memo)",
  );
  const memos = memoEncodings(config.memo);
  const deadline = Date.now() + config.logWaitMs;

  while (Date.now() < deadline) {
    const latestBlock = await client.getBlockNumber();
    const logs = (
      await Promise.all(
        memos.map((memo) =>
          client.getLogs({
            address: config.token,
            event,
            args: {
              from: payer,
              to: config.recipient,
              memo,
            },
            fromBlock,
            toBlock: latestBlock,
          }),
        ),
      )
    ).flat();

    const match = logs.find((log) => log.args.value === expectedValue);
    if (match) {
      return {
        transactionHash: match.transactionHash,
        blockNumber: match.blockNumber?.toString(),
      };
    }

    await sleep(1000);
  }

  throw new Error("no matching TransferWithMemo event observed");
}

module.exports = {
  runtimeEnv: defaultRuntimeEnv,
  verify,
};
