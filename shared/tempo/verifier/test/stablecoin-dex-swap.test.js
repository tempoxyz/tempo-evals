const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { encodeFunctionData, parseAbi, parseUnits } = require("viem");

const taker = "0x1111111111111111111111111111111111111111";
const dex = "0x2222222222222222222222222222222222222222";
const tokenIn = "0x3333333333333333333333333333333333333333";
const tokenOut = "0x4444444444444444444444444444444444444444";
const unrelated = "0x5555555555555555555555555555555555555555";
const transactionHash = `0x${"01".repeat(32)}`;
const amountIn = parseUnits("100", 6);
const swapAbi = parseAbi([
  "function swapExactAmountIn(address tokenIn, address tokenOut, uint128 amountIn, uint128 minAmountOut) returns (uint128 amountOut)",
]);

const tempoPath = require.resolve("../src/tempo");
require.cache[tempoPath] = {
  exports: {
    findEvent(receipt, address, _event, matches) {
      const args = {
        [dex]: { amountFilled: receipt.amountFilled, orderId: 1n, taker },
        [tokenIn]: { from: taker, to: receipt.inputRecipient, value: amountIn },
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

function fixture({
  amountFilled = amountIn,
  amountOut,
  inputRecipient = dex,
  minimumAmountOut,
  swapAmountIn = amountIn,
}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  const data = encodeFunctionData({
    abi: swapAbi,
    functionName: "swapExactAmountIn",
    args: [tokenIn, tokenOut, swapAmountIn, parseUnits(minimumAmountOut, 6)],
  });
  fs.writeFileSync(
    resultPath,
    JSON.stringify({ taker: { address: taker }, swapTransactionHash: transactionHash }),
  );
  return {
    client: {
      getTransaction: async () => ({ calls: [{ data, to: dex }] }),
      receipt: { amountFilled, amountOut, blockNumber: 2n, inputRecipient },
    },
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

test("rejects an exact input transfer sent outside the DEX", async () => {
  await assert.rejects(
    verify(fixture({ amountOut: amountIn, inputRecipient: unrelated, minimumAmountOut: "0" })),
    /does not spend the requested swap input/,
  );
});

test("rejects a smaller swap call paired with an unrelated exact input transfer", async () => {
  await assert.rejects(
    verify(fixture({
      amountFilled: 1n,
      amountOut: 1n,
      inputRecipient: unrelated,
      minimumAmountOut: "0",
      swapAmountIn: 1n,
    })),
    /does not request the configured swap/,
  );
});
