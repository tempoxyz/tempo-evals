// SYNCED FROM shared/tempo/verifier/src/cases/faucet-funded-transfer.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, waitForEvidence } = require("../tempo");

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_FAUCET_PRIVATE_KEY: config.faucetPrivateKey,
  };
}

function beforeLog(left, right) {
  return (
    left.blockNumber < right.blockNumber ||
    (left.blockNumber === right.blockNumber && left.logIndex < right.logIndex)
  );
}

async function verify({ client, config, fromBlock }) {
  const localnetFaucet = privateKeyToAccount(config.payerPrivateKey).address;
  const sender = privateKeyToAccount(config.faucetPrivateKey).address;
  const expectedValue = parseUnits(config.amount, config.decimals);
  const event = parseAbiItem("event Transfer(address indexed from, address indexed to, uint256 value)");

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const logs = await client.getLogs({
      address: config.token,
      event,
      args: {
        from: sender,
        to: config.recipient,
      },
      fromBlock,
      toBlock: latestBlock,
    });

    const match = logs.find((log) => log.args.value === expectedValue);
    if (!match) return null;

    const fundingLogs = await client.getLogs({
      address: config.token,
      event,
      args: {
        from: localnetFaucet,
        to: sender,
      },
      fromBlock,
      toBlock: match.blockNumber,
    });
    const funding = fundingLogs.find(
      (log) => log.args.value >= expectedValue && beforeLog(log, match),
    );

    return (
      funding &&
      blockEvidence(match, {
        localnetFaucet,
        fundedSender: sender,
        fundingTransactionHash: funding.transactionHash,
      })
    );
  }, "no matching faucet-funded transfer event observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
