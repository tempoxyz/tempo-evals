const { parseAbi, parseAbiItem } = require("viem");
const { expectAddress, expectHash, expectObject, readResult } = require("../result");
const { defaultRuntimeEnv } = require("../submission");
const { findEvent, receiptAfter, sameAddress, waitForEvidence } = require("../tempo");

const USER_TOKEN_SET = parseAbiItem("event UserTokenSet(address indexed user, address indexed token)");
const FEE_MANAGER = parseAbi(["function userTokens(address user) view returns (address)"]);

function result(config) {
  return readResult(config, (value) => {
    expectObject(config, value, ["payer", "setFeeTokenTransactionHash"], "result");
    expectObject(config, value.payer, ["address"], "payer");
    return {
      payer: expectAddress(config, value.payer.address, "payer.address"),
      transactionHash: expectHash(config, value.setFeeTokenTransactionHash, "setFeeTokenTransactionHash"),
    };
  });
}

function runtimeEnv(config) {
  return { ...defaultRuntimeEnv(config), TEMPO_FEE_MANAGER: config.feeManager, TEMPO_FEE_TOKEN: config.feeToken };
}

async function verify({ client, config, fromBlock }) {
  const { payer, transactionHash } = result(config);

  return waitForEvidence(config, async () => {
    const receipt = await receiptAfter(
      client,
      fromBlock,
      transactionHash,
      payer,
      "reported fee-token transaction",
    );
    if (!receipt) return null;

    const event = findEvent(receipt, config.feeManager, USER_TOKEN_SET, (args) =>
      sameAddress(args.user, payer) && sameAddress(args.token, config.feeToken),
    );
    if (!event) throw new Error("reported transaction did not set the requested fee token");

    const token = await client.readContract({
      address: config.feeManager,
      abi: FEE_MANAGER,
      functionName: "userTokens",
      args: [payer],
    });
    if (!sameAddress(token, config.feeToken)) return null;

    return { blockNumber: receipt.blockNumber.toString(), payer, token, transactionHash };
  }, "fee token was not set for the reported payer");
}

module.exports = { runtimeEnv, verify };
