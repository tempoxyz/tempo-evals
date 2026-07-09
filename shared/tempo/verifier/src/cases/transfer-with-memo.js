const fs = require("node:fs");
const { decodeEventLog, isAddress, parseAbiItem, parseUnits } = require("viem");
const { defaultRuntimeEnv } = require("../submission");
const { memoEncodings, sameAddress, waitForEvidence } = require("../tempo");

const TRANSFER_WITH_MEMO = parseAbiItem(
  "event TransferWithMemo(address indexed from, address indexed to, uint256 value, bytes32 indexed memo)",
);
const HASH_PATTERN = /^0x[0-9a-fA-F]{64}$/;

function resultError(config, observed) {
  const error = new Error(`invalid result artifact: ${observed}`);
  error.phase = "submission-result";
  error.expected = `${config.resultPath} matches the transfer output schema`;
  error.observed = observed;
  return error;
}

function hasExactKeys(value, keys) {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    Object.keys(value).length === keys.length &&
    keys.every((key) => Object.hasOwn(value, key))
  );
}

function readResult(config) {
  let result;
  try {
    result = JSON.parse(fs.readFileSync(config.resultPath, "utf8"));
  } catch (error) {
    throw resultError(config, error instanceof Error ? error.message : String(error));
  }

  if (!hasExactKeys(result, ["payer", "transferTransactionHash"])) {
    throw resultError(config, "expected payer and transferTransactionHash only");
  }
  if (!hasExactKeys(result.payer, ["address"])) {
    throw resultError(config, "payer must contain address only");
  }

  const payer = result.payer.address;
  const transactionHash = result?.transferTransactionHash;
  if (!isAddress(payer)) throw resultError(config, "payer.address must be an address");
  if (typeof transactionHash !== "string" || !HASH_PATTERN.test(transactionHash)) {
    throw resultError(config, "transferTransactionHash must be a transaction hash");
  }

  return { payer, transactionHash };
}

function hasTransfer(receipt, config, payer, expectedValue, memos) {
  return receipt.logs.some((log) => {
    if (!sameAddress(log.address, config.token)) return false;

    try {
      const decoded = decodeEventLog({
        abi: [TRANSFER_WITH_MEMO],
        data: log.data,
        topics: log.topics,
      });
      return (
        decoded.eventName === "TransferWithMemo" &&
        sameAddress(decoded.args.from, payer) &&
        sameAddress(decoded.args.to, config.recipient) &&
        decoded.args.value === expectedValue &&
        memos.has(decoded.args.memo.toLowerCase())
      );
    } catch {
      return false;
    }
  });
}

function runtimeEnv(config) {
  const env = defaultRuntimeEnv(config);
  if (config.feePayerPrivateKey) {
    env.TEMPO_FEE_PAYER_PRIVATE_KEY = config.feePayerPrivateKey;
    env.TEMPO_FEE_TOKEN = config.feeToken;
  }
  return env;
}

async function verify({ client, config, fromBlock }) {
  const { payer, transactionHash } = readResult(config);
  const expectedValue = parseUnits(config.amount, config.decimals);
  const memos = new Set(memoEncodings(config.memo).map((memo) => memo.toLowerCase()));

  return waitForEvidence(config, async () => {
    let receipt;
    try {
      receipt = await client.getTransactionReceipt({ hash: transactionHash });
    } catch {
      return null;
    }

    if (receipt.status !== "success") {
      throw new Error("reported transfer transaction did not succeed");
    }
    if (receipt.blockNumber <= fromBlock) {
      throw new Error("reported transfer transaction predates this evaluation");
    }
    if (!sameAddress(receipt.from, payer)) {
      throw new Error("reported transfer transaction was not sent by payer.address");
    }
    if (!hasTransfer(receipt, config, payer, expectedValue, memos)) {
      throw new Error("reported transaction does not contain the required TransferWithMemo event");
    }

    return {
      blockNumber: receipt.blockNumber.toString(),
      payer,
      transactionHash,
    };
  }, "reported transfer transaction was not observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
