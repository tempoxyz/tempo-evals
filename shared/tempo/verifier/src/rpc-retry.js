const { setTimeout: wait } = require("node:timers/promises");

const INSTALLED = Symbol.for("tempo-bench.rpc-retry");
const MAX_RETRIES = 5;
const RETRY_EXHAUSTED = "TEMPO_RPC_RETRY_EXHAUSTED";
const RETRYABLE_READ_STATUSES = new Set([408, 500, 502, 503, 504]);
const RATE_LIMIT_MESSAGE = /rate.?limit|too many requests|try again|exceeds? (?:the )?defined limit/i;
const TEMPO_RPC_HOST = "rpc.moderato.tempo.xyz";
// These are retried only after an explicit rate-limit rejection, never an ambiguous 5xx.
const RATE_LIMIT_ONLY_METHODS = new Set([
  "eth_sendRawTransaction",
  "eth_sendRawTransactionSync",
  "tempo_fundAddress",
]);
const READ_METHODS = new Set([
  "eth_blockNumber",
  "eth_call",
  "eth_chainId",
  "eth_estimateGas",
  "eth_feeHistory",
  "eth_gasPrice",
  "eth_maxPriorityFeePerGas",
  "eth_syncing",
  "web3_clientVersion",
]);

function isReadMethod(method) {
  return (
    (method.startsWith("eth_get") && method !== "eth_getFilterChanges") ||
    method.startsWith("net_") ||
    READ_METHODS.has(method)
  );
}

function requestKind(body) {
  if (typeof body !== "string") return null;
  try {
    const payload = JSON.parse(body);
    const requests = Array.isArray(payload) ? payload : [payload];
    if (requests.length === 0 || requests.some(({ method }) => typeof method !== "string")) {
      return null;
    }
    if (requests.every(({ method }) => isReadMethod(method))) return "read";
    if (requests.length === 1 && RATE_LIMIT_ONLY_METHODS.has(requests[0].method)) {
      return "rate-limit-only";
    }
    return null;
  } catch {
    return null;
  }
}

function isTempoRpc(input) {
  try {
    const value = typeof input === "object" && input?.url ? input.url : input;
    const url = new URL(value);
    return url.protocol === "https:" && url.hostname === TEMPO_RPC_HOST;
  } catch {
    return false;
  }
}

function isRateLimitError(error) {
  return (
    (error?.code === -32005 || error?.code === 429) &&
    RATE_LIMIT_MESSAGE.test(String(error.message))
  );
}

async function isRetryableResponse(response, kind) {
  if (response.status === 429) return true;
  if (kind === "read" && RETRYABLE_READ_STATUSES.has(response.status)) return true;
  try {
    const payload = await response.clone().json();
    const replies = Array.isArray(payload) ? payload : [payload];
    return replies.length > 0 && replies.every((reply) => isRateLimitError(reply?.error));
  } catch {
    return false;
  }
}

function isRpcRetryExhausted(error) {
  const seen = new Set();
  let current = error;
  while (current && typeof current === "object" && !seen.has(current)) {
    if (current.code === RETRY_EXHAUSTED) return true;
    seen.add(current);
    current = current.cause;
  }
  return false;
}

function withRpcRetries(
  fetchFn,
  sleep = (ms, signal) => wait(ms, undefined, { signal }),
) {
  return async (input, init) => {
    const kind = requestKind(init?.body);
    if (!isTempoRpc(input) || !kind) return fetchFn(input, init);

    for (let attempt = 0; ; attempt += 1) {
      const response = await fetchFn(input, init);
      if (!(await isRetryableResponse(response, kind))) return response;
      if (attempt >= MAX_RETRIES) {
        const error = new Error(`Tempo RPC remained unavailable after ${attempt + 1} attempts`);
        error.code = RETRY_EXHAUSTED;
        throw error;
      }
      const backoff = 100 * 2 ** attempt;
      await sleep(backoff + Math.floor(Math.random() * backoff), init?.signal);
    }
  };
}

function installRpcRetry() {
  if (typeof globalThis.fetch !== "function" || globalThis.fetch[INSTALLED]) return;
  const fetchWithRetries = withRpcRetries(globalThis.fetch);
  Object.defineProperty(fetchWithRetries, INSTALLED, { value: true });
  globalThis.fetch = fetchWithRetries;
}

module.exports = {
  installRpcRetry,
  isRpcRetryExhausted,
  withRpcRetries,
};
