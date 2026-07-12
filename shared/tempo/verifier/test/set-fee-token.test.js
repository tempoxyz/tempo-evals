const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { encodeFunctionData, parseAbi } = require("viem");

const { verify } = require("../src/cases/set-fee-token");

const payer = "0x1111111111111111111111111111111111111111";
const feeManager = "0x2222222222222222222222222222222222222222";
const feeToken = "0x3333333333333333333333333333333333333333";
const otherToken = "0x4444444444444444444444444444444444444444";
const transactionHash = `0x${"01".repeat(32)}`;
const feeManagerAbi = parseAbi(["function setUserToken(address token)"]);

function fixture(token = feeToken) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  fs.writeFileSync(
    resultPath,
    JSON.stringify({
      payer: { address: payer },
      setFeeTokenTransactionHash: transactionHash,
    }),
  );
  return {
    client: {
      getTransaction: async () => ({
        input: encodeFunctionData({ abi: feeManagerAbi, functionName: "setUserToken", args: [token] }),
        to: feeManager,
      }),
      getTransactionReceipt: async () => ({
        blockNumber: 2n,
        from: payer,
        status: "success",
      }),
      readContract: async () => feeToken,
    },
    config: { feeManager, feeToken, logWaitMs: 10, resultPath },
    fromBlock: 1n,
  };
}

test("accepts a successful idempotent fee-token call without an event", async () => {
  const evidence = await verify(fixture());

  assert.equal(evidence.payer, payer);
  assert.equal(evidence.token, feeToken);
  assert.equal(evidence.transactionHash, transactionHash);
});

test("rejects a fee-token call with the wrong token", async () => {
  await assert.rejects(verify(fixture(otherToken)), /did not request the expected fee token/);
});
