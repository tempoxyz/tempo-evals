// SYNCED FROM shared/tempo/verifier/src/submission.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { writeJson, writeText } = require("./logs");

function assertSubmissionShape(config) {
  const packageJson = path.join(config.workspace, "package.json");
  if (!fs.existsSync(packageJson)) {
    const error = new Error("submission did not create /app/package.json");
    error.phase = "submission-shape";
    error.expected = "submission creates /app/package.json";
    error.observed = "/app/package.json was missing";
    throw error;
  }
}

function stepLogFiles(name) {
  return [
    `${name}.stdout.txt`,
    `${name}.stderr.txt`,
    `${name}.status.json`,
  ];
}

function formatCommand(command, args) {
  return [command, ...args].join(" ");
}

function runStep(config, name, command, args, env = {}) {
  const result = spawnSync(command, args, {
    cwd: config.workspace,
    env: { ...process.env, ...env },
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    timeout: config.submissionTimeoutMs,
  });

  writeText(config, `${name}.stdout.txt`, result.stdout || "");
  writeText(config, `${name}.stderr.txt`, result.stderr || "");
  writeJson(config, `${name}.status.json`, {
    command,
    args,
    status: result.status,
    signal: result.signal,
    error: result.error?.message || null,
  });

  if (result.error) {
    result.error.phase = name;
    result.error.expected = `${formatCommand(command, args)} exits 0`;
    result.error.observed = result.error.message;
    result.error.logs = stepLogFiles(name);
    throw result.error;
  }
  if (result.status !== 0) {
    const error = new Error(`${name} failed with exit ${result.status}`);
    error.phase = name;
    error.expected = `${formatCommand(command, args)} exits 0`;
    error.observed = result.signal
      ? `terminated by signal ${result.signal}`
      : `exit ${result.status}`;
    error.logs = stepLogFiles(name);
    throw error;
  }
}

function defaultRuntimeEnv(config) {
  return {
    TEMPO_TOKEN: config.token,
    ...(config.recipient ? { TEMPO_RECIPIENT: config.recipient } : {}),
    ...(config.recipients.length > 0 ? { TEMPO_RECIPIENTS: JSON.stringify(config.recipients) } : {}),
    TEMPO_AMOUNT: config.amount,
    TEMPO_MEMO: config.memo,
    TEMPO_DECIMALS: String(config.decimals),
  };
}

function withRpcRetryEnv(env) {
  const retryPreload = `--require=${path.join(__dirname, "rpc-retry-preload.js")}`;
  return {
    ...env,
    NODE_OPTIONS: [env.NODE_OPTIONS ?? process.env.NODE_OPTIONS, retryPreload]
      .filter(Boolean)
      .join(" "),
  };
}

module.exports = {
  assertSubmissionShape,
  defaultRuntimeEnv,
  runStep,
  withRpcRetryEnv,
};
