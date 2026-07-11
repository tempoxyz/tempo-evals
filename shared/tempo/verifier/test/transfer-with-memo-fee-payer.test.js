const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { parseUnits } = require("viem");

const payer = "0x1111111111111111111111111111111111111111";
const recipient = "0x2222222222222222222222222222222222222222";
const token = "0x3333333333333333333333333333333333333333";
const transactionHash = `0x${"01".repeat(32)}`;

test("rejects using the payer as its own fee payer", async () => {
  const tempoPath = require.resolve("../src/tempo");
  require.cache[tempoPath] = {
    exports: {
      findEvent(_receipt, _address, _event, matches) {
        const args = { from: payer, to: recipient, value: parseUnits("0.19", 6), memo: "0x01" };
        return matches(args) ? { args } : null;
      },
      memoEncodings: () => ["0x01"],
      receiptAfter: async () => ({ blockNumber: 2n, feePayer: payer }),
      sameAddress: (left, right) => left.toLowerCase() === right.toLowerCase(),
      waitForEvidence: async (_config, check) => check(),
    },
  };
  delete require.cache[require.resolve("../src/cases/transfer-with-memo-fee-payer")];
  const { verify } = require("../src/cases/transfer-with-memo-fee-payer");

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  fs.writeFileSync(
    resultPath,
    JSON.stringify({
      payer: { address: payer },
      feePayer: { address: payer },
      transferTransactionHash: transactionHash,
    }),
  );

  await assert.rejects(
    verify({
      client: {
        request: async () => ({ type: "0x76", feePayerSignature: "0x01", feeToken: token }),
      },
      config: { resultPath, amount: "0.19", decimals: 6, memo: "memo", token, recipient, feeToken: token },
      fromBlock: 1n,
    }),
    /fee payer must be separate/,
  );
});
