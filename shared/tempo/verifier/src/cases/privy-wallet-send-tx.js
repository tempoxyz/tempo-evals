const { parseAbiItem, parseUnits } = require("viem");
const { expectAddress, expectHash, expectObject, expectText, readResult } = require("../result");
const { getWallet, requirePrivyAuth } = require("../privy");
const { defaultRuntimeEnv } = require("../submission");
const { findEvent, receiptAfter, sameAddress, waitForEvidence } = require("../tempo");

const TRANSFER = parseAbiItem("event Transfer(address indexed from, address indexed to, uint256 value)");

function result(config) {
  return readResult(config, (value) => {
    expectObject(config, value, ["wallet", "transferTransactionHash"], "result");
    expectObject(config, value.wallet, ["id", "address"], "wallet");
    return {
      walletId: expectText(config, value.wallet.id, "wallet.id"),
      address: expectAddress(config, value.wallet.address, "wallet.address"),
      transactionHash: expectHash(config, value.transferTransactionHash, "transferTransactionHash"),
    };
  });
}

function runtimeEnv(config) {
  return defaultRuntimeEnv(config);
}

async function verify({ client, config, fromBlock }) {
  requirePrivyAuth(config);
  const { walletId, address, transactionHash } = result(config);
  const amount = parseUnits(config.amount, config.decimals);

  const wallet = await getWallet(config, walletId);
  if (!sameAddress(wallet.address, address)) {
    throw new Error("reported wallet address does not match the Privy wallet");
  }
  if (wallet.chain_type !== "ethereum") {
    throw new Error("Privy wallet is not an ethereum wallet");
  }

  return waitForEvidence(config, async () => {
    const receipt = await receiptAfter(
      client,
      fromBlock,
      transactionHash,
      address,
      "reported transfer transaction",
    );
    if (!receipt) return null;
    const transfer = findEvent(receipt, config.token, TRANSFER, (args) =>
      sameAddress(args.from, address) &&
      sameAddress(args.to, config.recipient) &&
      args.value === amount,
    );
    if (!transfer) {
      throw new Error("reported transaction does not transfer the requested token amount");
    }
    return {
      blockNumber: receipt.blockNumber.toString(),
      walletId,
      payer: address,
      transactionHash,
    };
  }, "Privy wallet transfer was not observed");
}

module.exports = { runtimeEnv, verify };
