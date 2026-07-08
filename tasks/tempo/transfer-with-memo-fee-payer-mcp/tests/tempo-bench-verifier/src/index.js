// SYNCED FROM shared/tempo/verifier/src/index.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
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

    context = {
      phase: "rpc",
      expected: `Tempo RPC is reachable at ${config.rpcUrl}`,
      logs: [],
    };
    const client = createTempoClient(config);
    const fromBlock = await waitForRpc(client, config);

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
      phase: "submission-example",
      expected: "npm run example exits 0",
      logs: [
        "submission-example.stdout.txt",
        "submission-example.stderr.txt",
        "submission-example.status.json",
      ],
    };
    runStep(
      config,
      "submission-example",
      "npm",
      ["run", "example"],
      verifier.runtimeEnv(config),
    );
    scores.build = 1;
    scores.run = 1;

    context = {
      phase: "onchain-verification",
      expected: `${config.caseId} verifier observes required onchain evidence`,
      logs: ["details.json"],
    };
    const evidence = await verifier.verify({ client, config, fromBlock });
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
