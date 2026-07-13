const { parseAbiItem, parseUnits } = require("viem");
const { expectAddress, expectHash, expectObject, readResult } = require("../result");
const { defaultRuntimeEnv } = require("../submission");
const { findEvent, memoEncodings, receiptAfter, sameAddress, waitForEvidence } = require("../tempo");

const TRANSFER_WITH_MEMO = parseAbiItem(
  "event TransferWithMemo(address indexed from, address indexed to, uint256 value, bytes32 indexed memo)",
);

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
  return defaultRuntimeEnv(config);
}

async function verify({ client, config, fromBlock }) {
  const { payer, transactionHash } = result(config);
  const amount = parseUnits(config.amount, config.decimals);
  const memos = new Set(memoEncodings(config.memo).map((memo) => memo.toLowerCase()));

  return waitForEvidence(config, async () => {
    const receipt = await receiptAfter(
      client,
      fromBlock,
      transactionHash,
      payer,
      "reported transfer transaction",
    );
    if (!receipt) return null;

    const transfer = findEvent(receipt, config.token, TRANSFER_WITH_MEMO, (args) =>
      sameAddress(args.from, payer) &&
      sameAddress(args.to, config.recipient) &&
      args.value === amount &&
      memos.has(args.memo.toLowerCase()),
    );
    if (!transfer) throw new Error("reported transaction lacks the required TransferWithMemo event");

    return { blockNumber: receipt.blockNumber.toString(), payer, transactionHash };
  }, "reported transfer transaction was not observed");
}

module.exports = { runtimeEnv, verify };
