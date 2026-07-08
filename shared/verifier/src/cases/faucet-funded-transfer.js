// SYNCED FROM shared/verifier/src/cases/faucet-funded-transfer.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
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

async function verify({ client, config, fromBlock }) {
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
    return match && blockEvidence(match, { fundedSender: sender });
  }, "no matching faucet-funded transfer event observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
