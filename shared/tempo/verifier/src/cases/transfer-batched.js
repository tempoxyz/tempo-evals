const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, sameAddress, waitForEvidence } = require("../tempo");

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_RECIPIENTS: JSON.stringify(config.recipients),
  };
}

async function verify({ client, config, fromBlock }) {
  const payer = privateKeyToAccount(config.payerPrivateKey).address;
  const expectedValue = parseUnits(config.amount, config.decimals);
  const event = parseAbiItem("event Transfer(address indexed from, address indexed to, uint256 value)");

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const logsByRecipient = await Promise.all(
      config.recipients.map((recipient) =>
        client.getLogs({
          address: config.token,
          event,
          args: { from: payer, to: recipient },
          fromBlock,
          toBlock: latestBlock,
        }),
      ),
    );
    const matchingLogs = logsByRecipient.map((logs) =>
      logs.filter((log) => log.args.value === expectedValue),
    );
    if (matchingLogs.some((logs) => logs.length === 0)) return null;

    const transactionHashes = new Set(
      matchingLogs.flatMap((logs) => logs.map((log) => log.transactionHash.toLowerCase())),
    );
    const transactionHash = [...transactionHashes].find((hash) =>
      matchingLogs.every((logs) => logs.some((log) => sameAddress(log.transactionHash, hash))),
    );
    if (!transactionHash) return null;

    const match = matchingLogs[0].find((log) => sameAddress(log.transactionHash, transactionHash));
    return blockEvidence(match, {
      payer,
      recipientCount: config.recipients.length,
      recipients: config.recipients,
    });
  }, "no single transaction paid every configured recipient");
}

module.exports = {
  runtimeEnv,
  verify,
};
