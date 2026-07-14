const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const path = require("node:path");
const test = require("node:test");

const { withRpcRetryEnv } = require("../src/submission");
const { isRpcRetryExhausted, withRpcRetries } = require("../src/rpc-retry");
const { receiptAfter } = require("../src/tempo");

const RPC_URL = "https://rpc.moderato.tempo.xyz";

function rpcResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    headers: { "content-type": "application/json" },
    status,
  });
}

function rpcRequest(fetch, method, { params = ["0x01"], signal, url = RPC_URL } = {}) {
  return fetch(url, {
    body: JSON.stringify({ method, params }),
    method: "POST",
    signal,
  });
}

test("retries transient read-only JSON-RPC failures", async () => {
  const delays = [];
  let calls = 0;
  const fetch = withRpcRetries(
    async () => {
      calls += 1;
      if (calls === 1) return rpcResponse({ error: { code: -32005, message: "rate limited" } });
      if (calls === 2) return rpcResponse({ error: "unavailable" }, 503);
      return rpcResponse({ result: { status: "0x1" } });
    },
    async (ms) => delays.push(ms),
  );

  const response = await rpcRequest(fetch, "eth_getTransactionReceipt");

  assert.equal(calls, 3);
  assert.ok(delays[0] >= 100 && delays[0] < 200);
  assert.ok(delays[1] >= 200 && delays[1] < 400);
  assert.deepEqual(await response.json(), { result: { status: "0x1" } });
});

test("retries an identical signed transaction after an explicit rate limit", async () => {
  const bodies = [];
  const fetch = withRpcRetries(
    async (_input, init) => {
      bodies.push(init.body);
      return bodies.length < 3
        ? rpcResponse({ error: { code: -32005, message: "rate limited, try again" } })
        : rpcResponse({ result: { status: "0x1" } });
    },
    async () => {},
  );

  const response = await rpcRequest(fetch, "eth_sendRawTransactionSync");

  assert.equal(bodies.length, 3);
  assert.equal(new Set(bodies).size, 1);
  assert.deepEqual(await response.json(), { result: { status: "0x1" } });
});

test("retries an explicit faucet rate limit", async () => {
  let calls = 0;
  const fetch = withRpcRetries(
    async () => {
      calls += 1;
      return calls === 1
        ? rpcResponse({ error: { code: -32005, message: "Request exceeds defined limit." } })
        : rpcResponse({ result: "0x01" });
    },
    async () => {},
  );

  await rpcRequest(fetch, "tempo_fundAddress");
  assert.equal(calls, 2);
});

test("does not retry requests outside the safe scope", async () => {
  const rateLimit = () => rpcResponse({ error: { code: -32005, message: "rate limited" } });
  const cases = [
    { name: "higher-level write", method: "eth_sendTransaction", params: [{}], response: rateLimit },
    { name: "other RPC", method: "eth_getTransactionReceipt", response: rateLimit, url: "https://rpc.example" },
    {
      name: "non-rate-limit error",
      method: "eth_getTransactionReceipt",
      response: () => rpcResponse({ error: { code: -32005, message: "sequencer only" } }),
    },
    {
      name: "ambiguous raw write",
      method: "eth_sendRawTransactionSync",
      response: () => rpcResponse({ error: "unavailable" }, 503),
    },
    {
      name: "stateful filter read",
      method: "eth_getFilterChanges",
      response: () => rpcResponse({ error: "unavailable" }, 503),
    },
  ];

  for (const scenario of cases) {
    let calls = 0;
    const fetch = withRpcRetries(async () => {
      calls += 1;
      return scenario.response();
    });
    await rpcRequest(fetch, scenario.method, scenario);
    assert.equal(calls, 1, scenario.name);
  }
});

test("does not retry a partially successful batch", async () => {
  let calls = 0;
  const fetch = withRpcRetries(async () => {
    calls += 1;
    return rpcResponse([
      { result: "0x01" },
      { error: { code: -32005, message: "rate limited" } },
    ]);
  });

  await fetch(RPC_URL, {
    body: JSON.stringify([
      { method: "eth_getBlockByNumber", params: ["latest", false] },
      { method: "eth_getTransactionReceipt", params: ["0x01"] },
    ]),
    method: "POST",
  });
  assert.equal(calls, 1);
});

test("bounds retries and marks exhaustion", async () => {
  let calls = 0;
  const fetch = withRpcRetries(
    async () => {
      calls += 1;
      return rpcResponse({ error: { code: -32005, message: "try again" } });
    },
    async () => {},
  );

  await assert.rejects(
    rpcRequest(fetch, "eth_getTransactionReceipt"),
    (error) => isRpcRetryExhausted(error),
  );
  assert.equal(calls, 6);
});

test("receipt polling propagates only exhausted RPC retries", async () => {
  const exhausted = new Error("retry exhausted");
  exhausted.code = "TEMPO_RPC_RETRY_EXHAUSTED";
  const wrapped = new Error("HTTP request failed", { cause: exhausted });
  const client = {
    getTransactionReceipt: async () => {
      throw wrapped;
    },
  };

  await assert.rejects(
    receiptAfter(client, 0n, "0x01", null, "reported transaction"),
    (error) => isRpcRetryExhausted(error),
  );
  client.getTransactionReceipt = async () => {
    throw new Error("transaction not found");
  };
  assert.equal(await receiptAfter(client, 0n, "0x01", null, "reported transaction"), null);
});

test("stops retrying when the request is aborted", async () => {
  const controller = new AbortController();
  let calls = 0;
  const fetch = withRpcRetries(async () => {
    calls += 1;
    return rpcResponse({ error: { code: -32005, message: "rate limited" } });
  });

  const request = rpcRequest(fetch, "eth_getTransactionReceipt", { signal: controller.signal });
  controller.abort();

  await assert.rejects(request, { name: "AbortError" });
  assert.equal(calls, 1);
});

test("preloads retries into submission Node processes", () => {
  const previous = process.env.NODE_OPTIONS;
  process.env.NODE_OPTIONS = "--trace-warnings";
  try {
    const env = withRpcRetryEnv({});
    assert.equal(
      env.NODE_OPTIONS,
      `--trace-warnings --require=${path.join(__dirname, "../src/rpc-retry-preload.js")}`,
    );
    const result = spawnSync(
      process.execPath,
      ["-e", "process.stdout.write(String(Boolean(fetch[Symbol.for('tempo-bench.rpc-retry')])))"],
      { encoding: "utf8", env: { ...process.env, ...env } },
    );
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, "true");
  } finally {
    if (previous === undefined) delete process.env.NODE_OPTIONS;
    else process.env.NODE_OPTIONS = previous;
  }
});
