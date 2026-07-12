const { decodeFunctionData, parseAbi } = require("viem");
const { expectAddress, expectHash, expectObject, readResult } = require("../result");
const { defaultRuntimeEnv } = require("../submission");
const { receiptAfter, sameAddress, waitForEvidence } = require("../tempo");

const FEE_MANAGER = parseAbi([
  "function setUserToken(address token)",
  "function userTokens(address user) view returns (address)",
]);

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

    const transaction = await client.getTransaction({ hash: transactionHash });
    if (!sameAddress(transaction.to, config.feeManager)) {
      throw new Error("reported transaction did not call the Fee Manager");
    }
    try {
      const call = decodeFunctionData({ abi: FEE_MANAGER, data: transaction.input });
      if (call.functionName !== "setUserToken" || !sameAddress(call.args[0], config.feeToken)) {
        throw new Error();
      }
    } catch {
      throw new Error("reported transaction did not request the expected fee token");
    }

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
