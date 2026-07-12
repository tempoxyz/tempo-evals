const { decodeFunctionData, parseAbi, parseAbiItem, parseUnits } = require("viem");
const { expectAddress, expectHash, expectObject, readResult } = require("../result");
const { defaultRuntimeEnv } = require("../submission");
const { findEvent, receiptAfter, sameAddress, waitForEvidence } = require("../tempo");

const TRANSFER = parseAbi(["function transfer(address to, uint256 value)"]);
const TRANSFER_EVENT = parseAbiItem("event Transfer(address indexed from, address indexed to, uint256 value)");

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
    const requestedEveryPayment = config.recipients.every((recipient) =>
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
    if (!requestedEveryPayment) {
      throw new Error("reported transaction does not request payment to every configured recipient");
    }
    const deliveredEveryPayment = config.recipients.every((recipient) =>
      findEvent(receipt, config.token, TRANSFER_EVENT, (args) =>
        sameAddress(args.from, payer) &&
        sameAddress(args.to, recipient) &&
        args.value === expectedValue,
      ),
    );
    if (!deliveredEveryPayment) {
      throw new Error("reported transaction did not deliver payment to every configured recipient");
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
