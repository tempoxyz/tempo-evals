const { decodeFunctionData, parseAbi, parseUnits } = require("viem");
const { expectAddress, expectHash, expectObject, readResult } = require("../result");
const { defaultRuntimeEnv } = require("../submission");
const { receiptAfter, sameAddress, waitForEvidence } = require("../tempo");

const TRANSFER = parseAbi(["function transfer(address to, uint256 value)"]);

function result(config) {
  return readResult(config, (value) => {
    expectObject(config, value, ["payer", "transferTransactionHash"], "result");
    expectObject(config, value.payer, ["address"], "payer");
    return {
      payer: expectAddress(config, value.payer.address, "payer.address"),
      transactionHash: expectHash(config, value.transferTransactionHash, "transferTransactionHash"),
    };
  });
}

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_RECIPIENTS: JSON.stringify(config.recipients),
  };
}

async function verify({ client, config, fromBlock }) {
  const { payer, transactionHash } = result(config);
  const expectedValue = parseUnits(config.amount, config.decimals);

  return waitForEvidence(config, async () => {
    const receipt = await receiptAfter(
      client,
      fromBlock,
      transactionHash,
      payer,
      "reported batch transaction",
    );
    if (!receipt) return null;

    const transaction = await client.getTransaction({ hash: transactionHash });
    const paidEveryRecipient = config.recipients.every((recipient) =>
      transaction.calls?.some((call) => {
        if (!sameAddress(call.to, config.token)) return false;
        try {
          const decoded = decodeFunctionData({ abi: TRANSFER, data: call.data });
          return (
            decoded.functionName === "transfer" &&
            sameAddress(decoded.args[0], recipient) &&
            decoded.args[1] === expectedValue
          );
        } catch {
          return false;
        }
      }),
    );
    if (!paidEveryRecipient) {
      throw new Error("reported transaction does not pay every configured recipient");
    }

    return {
      blockNumber: receipt.blockNumber.toString(),
      payer,
      recipientCount: config.recipients.length,
      recipients: config.recipients,
      transactionHash,
    };
  }, "reported batch transaction was not observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
