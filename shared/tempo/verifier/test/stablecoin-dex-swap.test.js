const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { parseUnits } = require("viem");

const taker = "0x1111111111111111111111111111111111111111";
const dex = "0x2222222222222222222222222222222222222222";
const tokenIn = "0x3333333333333333333333333333333333333333";
const tokenOut = "0x4444444444444444444444444444444444444444";
const transactionHash = `0x${"01".repeat(32)}`;
const amountIn = parseUnits("100", 6);

const tempoPath = require.resolve("../src/tempo");
require.cache[tempoPath] = {
  exports: {
    findEvent(receipt, address, _event, matches) {
      const args = {
        [dex]: { orderId: 1n, taker },
        [tokenIn]: { from: taker, to: dex, value: amountIn },
        [tokenOut]: { from: dex, to: taker, value: receipt.amountOut },
      }[address];
      return matches(args) ? { args } : null;
    },
    receiptAfter: async (client) => client.receipt,
    sameAddress: (left, right) => left.toLowerCase() === right.toLowerCase(),
    waitForEvidence: async (_config, check) => check(),
  },
};
delete require.cache[require.resolve("../src/cases/stablecoin-dex-swap")];
const { verify } = require("../src/cases/stablecoin-dex-swap");

function fixture({ amountOut, minimumAmountOut }) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  fs.writeFileSync(
    resultPath,
    JSON.stringify({ taker: { address: taker }, swapTransactionHash: transactionHash }),
  );
  return {
    client: { receipt: { amountOut, blockNumber: 2n } },
    config: {
      decimals: 6,
      resultPath,
      stablecoinDex: dex,
      swapAmountIn: "100",
      swapMinAmountOut: minimumAmountOut,
      swapTokenIn: tokenIn,
      swapTokenOut: tokenOut,
    },
    fromBlock: 1n,
  };
}

test("accepts swap output equal to the configured minimum", async () => {
  const amountOut = parseUnits("99", 6);
  const evidence = await verify(fixture({ amountOut, minimumAmountOut: "99" }));

  assert.equal(evidence.transactionHash, transactionHash);
});

test("rejects swap output below the configured minimum", async () => {
  await assert.rejects(
    verify(fixture({ amountOut: parseUnits("98.999999", 6), minimumAmountOut: "99" })),
    /does not receive the requested swap output/,
  );
});

test("rejects zero swap output when the configured minimum is zero", async () => {
  await assert.rejects(
    verify(fixture({ amountOut: 0n, minimumAmountOut: "0" })),
    /does not receive the requested swap output/,
  );
});
