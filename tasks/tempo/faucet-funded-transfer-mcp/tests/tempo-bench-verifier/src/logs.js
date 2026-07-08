// SYNCED FROM shared/tempo/verifier/src/logs.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
const fs = require("node:fs");
const path = require("node:path");

function ensureLogDir(config) {
  fs.mkdirSync(config.logDir, { recursive: true });
}

function ensureArtifactDir(config) {
  fs.mkdirSync(config.artifactDir, { recursive: true });
}

function writeJson(config, fileName, value) {
  ensureLogDir(config);
  fs.writeFileSync(path.join(config.logDir, fileName), `${JSON.stringify(value, null, 2)}\n`);
}

function writeText(config, fileName, value) {
  ensureLogDir(config);
  fs.writeFileSync(path.join(config.logDir, fileName), value || "");
}

function writeArtifactText(config, fileName, value) {
  ensureArtifactDir(config);
  fs.writeFileSync(path.join(config.artifactDir, fileName), value || "");
}

function formatException(details) {
  const lines = [
    "Tempo verifier scored correctness 0.",
    `phase: ${details.phase || "unknown"}`,
    `reason: ${details.reason || "unknown"}`,
    `expected: ${details.expected || "unknown"}`,
    `observed: ${details.observed || "unknown"}`,
    `scores: ${JSON.stringify(details.scores || {})}`,
    "",
    "logs:",
  ];

  const logs = Array.isArray(details.logs) ? details.logs : [];
  for (const log of logs) {
    lines.push(`- /logs/verifier/${log}`);
  }
  lines.push("- /logs/verifier/details.json");
  return `${lines.join("\n")}\n`;
}

function writeException(config, details) {
  writeArtifactText(config, "exception.txt", formatException(details));
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
  ensureArtifactDir,
  ensureLogDir,
  writeArtifactText,
  writeException,
  writeJson,
  writeReward,
  writeText,
};
