// SYNCED FROM shared/verifier/src/cases/faucet-funded-transfer.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { blockEvidence, waitForEvidence } = require("../tempo");

function runtimeEnv(config) {
  return {
    TEMPO_RPC_URL: config.rpcUrl,
    TEMPO_TOKEN: config.token,
    TEMPO_FAUCET_PRIVATE_KEY: config.faucetPrivateKey,
    TEMPO_RECIPIENT: config.recipient,
    TEMPO_AMOUNT: config.amount,
    TEMPO_DECIMALS: String(config.decimals),
  };
}

async function verify({ client, config, fromBlock }) {
  const faucet = privateKeyToAccount(config.payerPrivateKey).address;
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
        from: faucet,
        to: sender,
      },
      fromBlock,
      toBlock: match.blockNumber,
    });
    const funding = fundingLogs.find((log) => log.args.value >= expectedValue);

    return (
      funding &&
      blockEvidence(match, {
        faucet,
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
