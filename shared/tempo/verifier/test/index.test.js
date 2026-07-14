const assert = require("node:assert/strict");
const test = require("node:test");

const { isRetryableVerifierFailure } = require("../src/index");

test("distinguishes RPC infrastructure failures from incorrect evidence", () => {
  const exhausted = new Error("retry exhausted");
  exhausted.code = "TEMPO_RPC_RETRY_EXHAUSTED";
  const wrapped = new Error("HTTP request failed", { cause: exhausted });

  assert.equal(isRetryableVerifierFailure(wrapped, { phase: "onchain-verification" }), true);
  assert.equal(isRetryableVerifierFailure(new Error("wrong recipient"), { phase: "onchain-verification" }), false);
  assert.equal(isRetryableVerifierFailure(new Error("unreachable"), { phase: "rpc" }), true);
});
