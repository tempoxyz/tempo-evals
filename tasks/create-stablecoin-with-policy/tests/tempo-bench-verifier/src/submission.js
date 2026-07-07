const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { writeJson, writeText } = require("./logs");

function assertSubmissionShape(config) {
  const packageJson = path.join(config.workspace, "package.json");
  if (!fs.existsSync(packageJson)) {
    throw new Error("submission did not create /app/package.json");
  }
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

  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${name} failed with exit ${result.status}`);
  }
}

function defaultRuntimeEnv(config) {
  const runtimeEnv = {
    TEMPO_RPC_URL: config.rpcUrl,
  };

  for (const [key, value] of [
    ["TEMPO_TOKEN", config.token],
    ["TEMPO_PAYER_PRIVATE_KEY", config.payerPrivateKey],
    ["TEMPO_RECIPIENT", config.recipient],
    ["TEMPO_AMOUNT", config.amount],
    ["TEMPO_MEMO", config.memo],
    ["TEMPO_DECIMALS", config.decimals === undefined ? undefined : String(config.decimals)],
  ]) {
    if (value !== undefined && value !== "") {
      runtimeEnv[key] = value;
    }
  }

  return runtimeEnv;
}

module.exports = {
  assertSubmissionShape,
  defaultRuntimeEnv,
  runStep,
};
