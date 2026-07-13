// SYNCED FROM shared/tempo/verifier/src/index.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
const fs = require("node:fs");
const { readConfig, redactedConfig } = require("./config");
const { writeException, writeJson, writeReward } = require("./logs");
const { assertSubmissionShape, runStep } = require("./submission");
const { createTempoClient, waitForRpc } = require("./tempo");
const cases = require("./cases");

function errorValue(error, key) {
  return error && typeof error === "object" && key in error ? error[key] : null;
}

function errorReason(error) {
  return error instanceof Error ? error.message : String(error);
}

function failureDetails(config, error, context, scores) {
  const reason = errorReason(error);
  return {
    ok: false,
    phase: errorValue(error, "phase") || context.phase,
    reason,
    expected: errorValue(error, "expected") || context.expected,
    observed: errorValue(error, "observed") || reason,
    logs: errorValue(error, "logs") || context.logs || [],
    scores,
    fixture: redactedConfig(config),
  };
}

async function main() {
  const config = readConfig();
  const verifier = cases[config.caseId];
  const scores = { build: 0, run: 0, onchain: 0 };
  let context = {
    phase: "case-selection",
    expected: "TEMPO_BENCH_CASE maps to a supported verifier case",
    logs: [],
  };

  try {
    if (!verifier) throw new Error(`unsupported Tempo bench case: ${config.caseId}`);

    context = {
      phase: "submission-shape",
      expected: "submission creates /app/package.json",
      logs: [],
    };
    assertSubmissionShape(config);
    fs.rmSync(config.resultPath, { force: true });

    // Cases that only verify against external APIs (e.g. Privy) opt out of
    // the Tempo RPC dependency with `needsChain: false`.
    const needsChain = verifier.needsChain !== false;
    let client = null;
    let fromBlock = null;
    if (needsChain) {
      context = {
        phase: "rpc",
        expected: "Tempo testnet RPC is reachable",
        logs: [],
      };
      client = createTempoClient();
      fromBlock = await waitForRpc(client, config);
    }
    const startedAt = Date.now();

    context = {
      phase: "submission-npm-install",
      expected: "npm install --silent exits 0",
      logs: [
        "submission-npm-install.stdout.txt",
        "submission-npm-install.stderr.txt",
        "submission-npm-install.status.json",
      ],
    };
    runStep(config, "submission-npm-install", "npm", ["install", "--silent"]);
    context = {
      phase: "submission-eval",
      expected: "npm run eval exits 0",
      logs: [
        "submission-eval.stdout.txt",
        "submission-eval.stderr.txt",
        "submission-eval.status.json",
      ],
    };
    runStep(
      config,
      "submission-eval",
      "npm",
      ["run", "eval"],
      verifier.runtimeEnv(config),
    );
    scores.build = 1;
    scores.run = 1;

    context = {
      phase: "onchain-verification",
      expected: `${config.caseId} verifier observes required onchain evidence`,
      logs: ["details.json"],
    };
    const evidence = await verifier.verify({ client, config, fromBlock, startedAt });
    scores.onchain = 1;

    writeJson(config, "details.json", {
      ok: true,
      reason: "observed expected onchain evidence",
      evidence,
      fixture: redactedConfig(config),
    });
    writeReward(config, { reward: 1, ...scores });
  } catch (error) {
    const details = failureDetails(config, error, context, scores);
    writeJson(config, "details.json", details);
    writeException(config, details);
    writeReward(config, { reward: 0, ...scores });
  }
}

module.exports = {
  main,
};
