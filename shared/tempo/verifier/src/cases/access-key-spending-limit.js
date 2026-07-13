const {
  decodeFunctionData,
  parseAbiItem,
  parseUnits,
  toFunctionSelector,
} = require("viem");
const { Actions, Addresses } = require("viem/tempo");
const {
  expectAddress,
  expectHash,
  expectObject,
  expectUint,
  readResult,
} = require("../result");
const { defaultRuntimeEnv } = require("../submission");
const { findEvent, receiptAfter, sameAddress, waitForEvidence } = require("../tempo");

const KEY_AUTHORIZED = parseAbiItem(
  "event KeyAuthorized(address indexed account, address indexed publicKey, uint8 signatureType, uint64 expiry)",
);
const ACCESS_KEY_SPEND = parseAbiItem(
  "event AccessKeySpend(address indexed account, address indexed publicKey, address indexed token, uint256 amount, uint256 remainingLimit)",
);
const TRANSFER = parseAbiItem(
  "event Transfer(address indexed from, address indexed to, uint256 value)",
);
const TRANSFER_FUNCTION = parseAbiItem("function transfer(address to, uint256 amount) returns (bool)");
const SPENDING_LIMIT_EXCEEDED = toFunctionSelector("SpendingLimitExceeded()");

function result(config) {
  return readResult(config, (value) => {
    expectObject(
      config,
      value,
      [
        "payer",
        "accessKey",
        "authorizationTransactionHash",
        "transferTransactionHash",
        "overLimitTransactionHash",
        "remainingLimit",
      ],
      "result",
    );
    expectObject(config, value.payer, ["address"], "payer");
    expectObject(config, value.accessKey, ["address"], "accessKey");
    return {
      payer: expectAddress(config, value.payer.address, "payer.address"),
      accessKey: expectAddress(config, value.accessKey.address, "accessKey.address"),
      authorizationTransactionHash: expectHash(
        config,
        value.authorizationTransactionHash,
        "authorizationTransactionHash",
      ),
      transferTransactionHash: expectHash(
        config,
        value.transferTransactionHash,
        "transferTransactionHash",
      ),
      overLimitTransactionHash: expectHash(
        config,
        value.overLimitTransactionHash,
        "overLimitTransactionHash",
      ),
      remainingLimit: BigInt(expectUint(config, value.remainingLimit, "remainingLimit")),
    };
  });
}

function after(left, right) {
  return (
    left.blockNumber > right.blockNumber ||
    (left.blockNumber === right.blockNumber && left.transactionIndex > right.transactionIndex)
  );
}

function keychainSignature(transaction, payer, accessKey) {
  const signature = transaction.signature;
  return (
    transaction.type === "tempo" &&
    transaction.typeHex === "0x76" &&
    signature?.type === "keychain" &&
    sameAddress(signature.userAddress, payer) &&
    sameAddress(signature.keyId, accessKey)
  );
}

async function revertedReceiptAfter(client, fromBlock, hash, from) {
  let receipt;
  try {
    receipt = await client.getTransactionReceipt({ hash });
  } catch {
    return null;
  }
  if (receipt.status !== "reverted") {
    throw new Error("reported over-limit transaction did not revert");
  }
  if (receipt.blockNumber <= fromBlock) {
    throw new Error("reported over-limit transaction predates this evaluation");
  }
  if (!sameAddress(receipt.from, from)) {
    throw new Error("reported over-limit transaction was not sent by the payer");
  }
  return receipt;
}

function runtimeEnv(config) {
  return defaultRuntimeEnv(config);
}

async function verify({ client, config, fromBlock }) {
  const {
    payer,
    accessKey,
    authorizationTransactionHash,
    transferTransactionHash,
    overLimitTransactionHash,
    remainingLimit,
  } = result(config);
  if (sameAddress(payer, accessKey)) {
    throw new Error("reported access key must be separate from the payer");
  }
  if (!config.spendingLimit || !config.spendingPeriod || !config.overLimitAmount) {
    throw new Error(
      "TEMPO_SPENDING_LIMIT, TEMPO_SPENDING_PERIOD, and TEMPO_OVER_LIMIT_AMOUNT are required",
    );
  }
  const limit = parseUnits(config.spendingLimit, config.decimals);
  const period = Number(config.spendingPeriod);
  const amount = parseUnits(config.amount, config.decimals);
  const overLimitAmount = parseUnits(config.overLimitAmount, config.decimals);
  if (!Number.isSafeInteger(period) || period < 0) {
    throw new Error("configured spending period must be a non-negative integer");
  }
  if (amount > limit) {
    throw new Error("configured transfer amount exceeds the spending limit");
  }

  return waitForEvidence(config, async () => {
    const authorizationReceipt = await receiptAfter(
      client,
      fromBlock,
      authorizationTransactionHash,
      payer,
      "reported access key authorization transaction",
    );
    if (!authorizationReceipt) return null;

    const transferReceipt = await receiptAfter(
      client,
      fromBlock,
      transferTransactionHash,
      payer,
      "reported transfer transaction",
    );
    if (!transferReceipt) return null;

    const overLimitReceipt = await revertedReceiptAfter(
      client,
      fromBlock,
      overLimitTransactionHash,
      payer,
    );
    if (!overLimitReceipt) return null;
    if (after(authorizationReceipt, transferReceipt)) {
      throw new Error("reported access key authorization happened after the transfer");
    }
    if (!after(overLimitReceipt, transferReceipt)) {
      throw new Error("reported over-limit transaction did not happen after the successful transfer");
    }

    const authorization = findEvent(
      authorizationReceipt,
      Addresses.accountKeychain,
      KEY_AUTHORIZED,
      (args) => sameAddress(args.account, payer) && sameAddress(args.publicKey, accessKey),
    );
    if (!authorization) {
      throw new Error("reported authorization transaction did not authorize the access key");
    }

    const authorizationTransaction = await client.getTransaction({
      hash: authorizationTransactionHash,
    });
    const keyAuthorization = authorizationTransaction.keyAuthorization;
    const authorizationLimits = keyAuthorization?.limits;
    if (
      authorizationTransaction.type !== "tempo" ||
      authorizationTransaction.typeHex !== "0x76" ||
      !sameAddress(keyAuthorization?.address, accessKey) ||
      !Array.isArray(authorizationLimits) ||
      authorizationLimits.length !== 1 ||
      !sameAddress(authorizationLimits[0].token, config.token) ||
      authorizationLimits[0].limit !== limit ||
      Number(authorizationLimits[0].period ?? 0) !== period
    ) {
      throw new Error("reported authorization transaction does not contain the configured limit");
    }

    const initialMetadata = await Actions.accessKey.getMetadata(client, {
      account: payer,
      accessKey,
      blockNumber: authorizationReceipt.blockNumber,
    });
    const initialLimit = await Actions.accessKey.getRemainingLimit(client, {
      account: payer,
      accessKey,
      token: config.token,
      blockNumber: authorizationReceipt.blockNumber,
    });
    if (
      initialMetadata.spendPolicy !== "limited" ||
      initialMetadata.isRevoked ||
      initialLimit.remaining !== limit
    ) {
      throw new Error("reported access key was not authorized with the configured onchain limit");
    }

    const transferTransaction = await client.getTransaction({ hash: transferTransactionHash });
    if (!keychainSignature(transferTransaction, payer, accessKey)) {
      throw new Error("reported transfer was not signed by the authorized access key");
    }

    const transfer = findEvent(transferReceipt, config.token, TRANSFER, (args) =>
      sameAddress(args.from, payer) &&
      sameAddress(args.to, config.recipient) &&
      args.value === amount,
    );
    if (!transfer) {
      throw new Error("reported transaction does not transfer the requested token amount");
    }

    const spend = findEvent(
      transferReceipt,
      Addresses.accountKeychain,
      ACCESS_KEY_SPEND,
      (args) =>
        sameAddress(args.account, payer) &&
        sameAddress(args.publicKey, accessKey) &&
        sameAddress(args.token, config.token) &&
        args.amount === amount &&
        args.remainingLimit < limit,
    );
    if (!spend) {
      throw new Error("account keychain did not record the successful transfer against the limit");
    }

    const limitAfterTransfer = await Actions.accessKey.getRemainingLimit(client, {
      account: payer,
      accessKey,
      token: config.token,
      blockNumber: transferReceipt.blockNumber,
    });
    if (limitAfterTransfer.remaining > limit - amount || overLimitAmount <= limitAfterTransfer.remaining) {
      throw new Error("configured over-limit amount did not exceed the post-transfer allowance");
    }

    const overLimitTransaction = await client.getTransaction({ hash: overLimitTransactionHash });
    if (!keychainSignature(overLimitTransaction, payer, accessKey)) {
      throw new Error("reported over-limit transaction was not signed by the authorized access key");
    }
    if (!Array.isArray(overLimitTransaction.calls) || overLimitTransaction.calls.length !== 1) {
      throw new Error("reported over-limit transaction must contain exactly one call");
    }
    const [overLimitCall] = overLimitTransaction.calls;
    let decodedOverLimitCall;
    try {
      decodedOverLimitCall = decodeFunctionData({
        abi: [TRANSFER_FUNCTION],
        data: overLimitCall.data,
      });
    } catch {
      throw new Error("reported over-limit transaction does not call TIP-20 transfer");
    }
    if (
      !sameAddress(overLimitCall.to, config.token) ||
      decodedOverLimitCall.functionName !== "transfer" ||
      !sameAddress(decodedOverLimitCall.args[0], config.recipient) ||
      decodedOverLimitCall.args[1] !== overLimitAmount
    ) {
      throw new Error("reported over-limit transaction does not contain the configured transfer");
    }

    const rejectedTransfer = findEvent(overLimitReceipt, config.token, TRANSFER, (args) =>
      sameAddress(args.from, payer) &&
      sameAddress(args.to, config.recipient) &&
      args.value === overLimitAmount,
    );
    if (rejectedTransfer) {
      throw new Error("over-limit transfer unexpectedly reached the configured recipient");
    }

    const trace = await client.request({
      method: "debug_traceTransaction",
      params: [overLimitTransactionHash, {}],
    });
    if (
      trace?.failed !== true ||
      typeof trace.returnValue !== "string" ||
      trace.returnValue.toLowerCase() !== SPENDING_LIMIT_EXCEEDED.toLowerCase()
    ) {
      throw new Error("reported over-limit transaction did not revert with SpendingLimitExceeded()");
    }

    const currentLimit = await Actions.accessKey.getRemainingLimit(client, {
      account: payer,
      accessKey,
      token: config.token,
    });
    if (currentLimit.remaining !== remainingLimit || remainingLimit > limitAfterTransfer.remaining) {
      throw new Error("reported remaining limit does not match the onchain account keychain state");
    }

    return {
      blockNumber: overLimitReceipt.blockNumber.toString(),
      payer,
      accessKey,
      limit: limit.toString(),
      amount: amount.toString(),
      overLimitAmount: overLimitAmount.toString(),
      remainingLimit: remainingLimit.toString(),
      authorizationTransactionHash,
      transferTransactionHash,
      overLimitTransactionHash,
    };
  }, "access key spending limit, transfer, and onchain rejection were not observed");
}

module.exports = { runtimeEnv, verify };
