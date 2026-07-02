const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, waitForEvidence } = require("../tempo");

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_MULTI_RECIPIENTS: config.multiRecipients.join(","),
    TEMPO_MULTI_AMOUNTS: config.multiAmounts.join(","),
  };
}

function expectedTransfers(config) {
  if (config.multiRecipients.length !== config.multiAmounts.length) {
    throw new Error("TEMPO_MULTI_RECIPIENTS and TEMPO_MULTI_AMOUNTS must have the same length");
  }
  return config.multiRecipients.map((recipient, index) => ({
    recipient,
    amount: parseUnits(config.multiAmounts[index], config.decimals),
  }));
}

async function verify({ client, config, fromBlock }) {
  const payer = privateKeyToAccount(config.payerPrivateKey).address;
  const transfers = expectedTransfers(config);
  const event = parseAbiItem("event Transfer(address indexed from, address indexed to, uint256 value)");

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const matches = [];
    for (const transfer of transfers) {
      const logs = await client.getLogs({
        address: config.token,
        event,
        args: {
          from: payer,
          to: transfer.recipient,
        },
        fromBlock,
        toBlock: latestBlock,
      });
      const match = logs.find((log) => log.args.value === transfer.amount);
      if (!match) return null;
      matches.push(match);
    }

    const transactionHash = matches[0]?.transactionHash;
    if (!transactionHash || !matches.every((match) => match.transactionHash === transactionHash)) {
      return null;
    }

    const transaction = await client.request({
      method: "eth_getTransactionByHash",
      params: [transactionHash],
    });
    if (!Array.isArray(transaction?.calls) || transaction.calls.length < transfers.length) {
      return null;
    }

    return blockEvidence(matches[0], {
      recipients: transfers.map((transfer) => transfer.recipient),
      amounts: transfers.map((transfer) => transfer.amount.toString()),
      callCount: transaction.calls.length,
    });
  }, "expected multiparty transfers were not observed in one Tempo transaction");
}

module.exports = {
  runtimeEnv,
  verify,
};
