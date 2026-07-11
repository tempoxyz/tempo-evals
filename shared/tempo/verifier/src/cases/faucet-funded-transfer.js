const { parseAbiItem, parseUnits, zeroAddress } = require("viem");
const { expectAddress, expectHash, expectHashes, expectObject, readResult } = require("../result");
const { defaultRuntimeEnv } = require("../submission");
const { findEvent, receiptAfter, sameAddress, waitForEvidence } = require("../tempo");

const TRANSFER = parseAbiItem("event Transfer(address indexed from, address indexed to, uint256 value)");

function result(config) {
  return readResult(config, (value) => {
    expectObject(
      config,
      value,
      ["payer", "fundingTransactionHashes", "transferTransactionHash"],
      "result",
    );
    expectObject(config, value.payer, ["address"], "payer");
    return {
      payer: expectAddress(config, value.payer.address, "payer.address"),
      fundingTransactionHashes: expectHashes(config, value.fundingTransactionHashes, "fundingTransactionHashes"),
      transactionHash: expectHash(config, value.transferTransactionHash, "transferTransactionHash"),
    };
  });
}

function before(left, right) {
  return (
    left.blockNumber < right.blockNumber ||
    (left.blockNumber === right.blockNumber && left.transactionIndex < right.transactionIndex)
  );
}

function runtimeEnv(config) {
  return defaultRuntimeEnv(config);
}

async function verify({ client, config, fromBlock }) {
  const { payer, fundingTransactionHashes, transactionHash } = result(config);
  const amount = parseUnits(config.amount, config.decimals);

  return waitForEvidence(config, async () => {
    const transferReceipt = await receiptAfter(
      client,
      fromBlock,
      transactionHash,
      payer,
      "reported transfer transaction",
    );
    if (!transferReceipt) return null;
    const transfer = findEvent(transferReceipt, config.token, TRANSFER, (args) =>
      sameAddress(args.from, payer) &&
      sameAddress(args.to, config.recipient) &&
      args.value === amount,
    );
    if (!transfer) throw new Error("reported transaction does not transfer the requested token amount");

    for (const hash of fundingTransactionHashes) {
      const receipt = await receiptAfter(client, fromBlock, hash, null, "reported faucet transaction");
      if (!receipt) return null;
      const funding = findEvent(receipt, config.token, TRANSFER, (args) =>
        sameAddress(args.from, zeroAddress) && sameAddress(args.to, payer) && args.value >= amount,
      );
      if (funding && before(receipt, transferReceipt)) {
        return {
          blockNumber: transferReceipt.blockNumber.toString(),
          payer,
          fundingTransactionHash: hash,
          transactionHash,
        };
      }
    }
    throw new Error("reported faucet transactions did not fund the transfer payer");
  }, "faucet-funded transfer was not observed");
}

module.exports = { runtimeEnv, verify };
