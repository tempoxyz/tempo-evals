function env(name, fallback = "") {
  const value = process.env[name];
  return value && value.length > 0 ? value : fallback;
}

function requiredEnv(name) {
  const value = env(name);
  if (!value) throw new Error(`missing required environment variable: ${name}`);
  return value;
}

function numberEnv(name) {
  const value = Number(requiredEnv(name));
  if (!Number.isFinite(value)) throw new Error(`invalid numeric environment variable: ${name}`);
  return value;
}

function readConfig() {
  return {
    caseId: env("TEMPO_BENCH_CASE", "transfer-with-memo"),
    workspace: env("TEMPO_BENCH_WORKSPACE", "/app"),
    logDir: env("TEMPO_BENCH_LOG_DIR", "/logs/verifier"),
    rpcUrl: requiredEnv("TEMPO_RPC_URL"),
    token: requiredEnv("TEMPO_TOKEN"),
    payerPrivateKey: requiredEnv("TEMPO_PAYER_PRIVATE_KEY"),
    recipient: requiredEnv("TEMPO_RECIPIENT"),
    amount: requiredEnv("TEMPO_AMOUNT"),
    memo: requiredEnv("TEMPO_MEMO"),
    decimals: numberEnv("TEMPO_DECIMALS"),
    submissionTimeoutMs: Number(env("TEMPO_BENCH_SUBMISSION_TIMEOUT_MS", "180000")),
    rpcWaitMs: Number(env("TEMPO_BENCH_RPC_WAIT_MS", "60000")),
    logWaitMs: Number(env("TEMPO_BENCH_LOG_WAIT_MS", "30000")),
  };
}

function redactedConfig(config) {
  return {
    ...config,
    payerPrivateKey: "<redacted>",
  };
}

module.exports = {
  readConfig,
  redactedConfig,
};
