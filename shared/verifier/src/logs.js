// SYNCED FROM shared/verifier/src/logs.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
const fs = require("node:fs");
const path = require("node:path");

function ensureLogDir(config) {
  fs.mkdirSync(config.logDir, { recursive: true });
}

function writeJson(config, fileName, value) {
  ensureLogDir(config);
  fs.writeFileSync(path.join(config.logDir, fileName), `${JSON.stringify(value, null, 2)}\n`);
}

function writeText(config, fileName, value) {
  ensureLogDir(config);
  fs.writeFileSync(path.join(config.logDir, fileName), value || "");
}

function writeReward(config, scores) {
  const rewardFile = process.env.TEMPO_BENCH_INTERNAL_REWARD_FILE;
  if (rewardFile) {
    ensureLogDir(config);
    fs.writeFileSync(rewardFile, `${JSON.stringify(scores, null, 2)}\n`);
    return;
  }

  writeJson(config, "reward.json", scores);
}

module.exports = {
  ensureLogDir,
  writeJson,
  writeReward,
  writeText,
};
