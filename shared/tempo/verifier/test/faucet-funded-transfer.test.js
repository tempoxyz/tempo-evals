const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { parseUnits } = require("viem");

const payer = "0x1111111111111111111111111111111111111111";
const recipient = "0x2222222222222222222222222222222222222222";
const sender = "0x3333333333333333333333333333333333333333";
const token = "0x4444444444444444444444444444444444444444";
const fundingHash = `0x${"01".repeat(32)}`;
const transferHash = `0x${"02".repeat(32)}`;

test("rejects an ordinary transfer reported as faucet funding", async () => {
  const amount = parseUnits("0.23", 6);
  const tempoPath = require.resolve("../src/tempo");
  require.cache[tempoPath] = {
    exports: {
      findEvent(receipt, _address, _event, matches) {
        const args = receipt.kind === "funding"
          ? { from: sender, to: payer, value: amount }
          : { from: payer, to: recipient, value: amount };
        return matches(args) ? { args } : null;
      },
      receiptAfter: async (_client, _fromBlock, hash) =>
        hash === fundingHash
          ? { kind: "funding", blockNumber: 2n, transactionIndex: 0 }
          : { kind: "transfer", blockNumber: 3n, transactionIndex: 0 },
      sameAddress: (left, right) => left.toLowerCase() === right.toLowerCase(),
      waitForEvidence: async (_config, check) => check(),
    },
  };
  delete require.cache[require.resolve("../src/cases/faucet-funded-transfer")];
  const { verify } = require("../src/cases/faucet-funded-transfer");

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  fs.writeFileSync(
    resultPath,
    JSON.stringify({
      payer: { address: payer },
      fundingTransactionHashes: [fundingHash],
      transferTransactionHash: transferHash,
    }),
  );

  await assert.rejects(
    verify({
      client: {},
      config: { resultPath, amount: "0.23", decimals: 6, token, recipient },
      fromBlock: 1n,
    }),
    /reported faucet transactions did not fund the transfer payer/,
  );
});
