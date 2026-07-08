// AUTO-GENERATED FROM shared/verifier/src/index.js BY npm run sync. DO NOT EDIT MANUALLY.
const { readConfig, redactedConfig } = require("./config");
const { writeJson, writeReward } = require("./logs");
const { assertSubmissionShape, runStep } = require("./submission");
const { createTempoClient, waitForRpc } = require("./tempo");
const cases = require("./cases");

async function main() {
  const config = readConfig();
  const verifier = cases[config.caseId];
  const scores = { build: 0, run: 0, onchain: 0 };

  try {
    if (!verifier) throw new Error(`unsupported Tempo bench case: ${config.caseId}`);

    assertSubmissionShape(config);

    const client = createTempoClient(config);
    const fromBlock = await waitForRpc(client, config);

    runStep(config, "submission-npm-install", "npm", ["install", "--silent"]);
    runStep(config, "submission-build", "npm", ["run", "build"]);
    scores.build = 1;

    runStep(config, "submission-run", "npm", ["run", "run"], verifier.runtimeEnv(config));
    scores.run = 1;

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
    writeJson(config, "details.json", {
      ok: false,
      reason: error instanceof Error ? error.message : String(error),
      fixture: redactedConfig(config),
    });
    writeReward(config, { reward: 0, ...scores });
  }
}

module.exports = {
  main,
};
