#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const tasksDir = path.join(root, "tasks");

function relativeSymlinkTarget(destination, source) {
  return path.relative(path.dirname(destination), source);
}

function removePath(target) {
  try {
    const stat = fs.lstatSync(target);
    if (stat.isDirectory() && !stat.isSymbolicLink()) {
      fs.rmSync(target, { recursive: true, force: true });
    } else {
      fs.unlinkSync(target);
    }
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
}

function copyDir(source, destination) {
  removePath(destination);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.cpSync(source, destination, {
    recursive: true,
    filter: (sourcePath) =>
      !sourcePath.includes("node_modules") && !sourcePath.endsWith("package-lock.json"),
  });
}

function copyFile(source, destination) {
  removePath(destination);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.copyFileSync(source, destination);
}

function writeFile(destination, content) {
  removePath(destination);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.writeFileSync(destination, content);
}

function copyVerifier(source, destination, caseId) {
  fs.rmSync(destination, { recursive: true, force: true });
  copyFile(path.join(source, "package.json"), path.join(destination, "package.json"));
  copyDir(path.join(source, "bin"), path.join(destination, "bin"));

  const sourceSrc = path.join(source, "src");
  const destinationSrc = path.join(destination, "src");
  for (const entry of fs.readdirSync(sourceSrc, { withFileTypes: true })) {
    if (entry.isFile()) {
      copyFile(path.join(sourceSrc, entry.name), path.join(destinationSrc, entry.name));
    }
  }

  copyFile(
    path.join(sourceSrc, `cases/${caseId}.js`),
    path.join(destinationSrc, `cases/${caseId}.js`),
  );
  writeFile(
    path.join(destinationSrc, "cases/index.js"),
    `module.exports = {\n  ${JSON.stringify(caseId)}: require("./${caseId}"),\n};\n`,
  );
}

function assertTaskRewardKit(taskDir) {
  for (const relativePath of [
    "tests/reward.toml",
    "tests/criteria/check.py",
    "tests/e2e/check.py",
  ]) {
    const absolutePath = path.join(taskDir, relativePath);
    if (!fs.existsSync(absolutePath)) {
      throw new Error(`Missing task-local RewardKit file: ${absolutePath}`);
    }
  }
}

function syncRewardKit(taskDir) {
  removePath(path.join(taskDir, "tests/reward"));
  assertTaskRewardKit(taskDir);
  copyFile(
    path.join(root, "shared/rewardkit/verify-tempo.sh"),
    path.join(taskDir, "tests/e2e/verify-tempo.sh"),
  );
  fs.chmodSync(path.join(taskDir, "tests/e2e/verify-tempo.sh"), 0o755);
}

function linkDir(source, destination) {
  removePath(destination);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.symlinkSync(relativeSymlinkTarget(destination, source), destination, "dir");
}

function linkFile(source, destination) {
  removePath(destination);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.symlinkSync(relativeSymlinkTarget(destination, source), destination, "file");
}

function readStringTable(filePath, tableName) {
  const values = {};
  let currentTable = "";

  for (const line of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const tableMatch = line.match(/^\s*\[([^\]]+)\]\s*$/);
    if (tableMatch) {
      currentTable = tableMatch[1];
      continue;
    }

    if (currentTable !== tableName) continue;

    const valueMatch = line.match(
      /^\s*([A-Z0-9_]+)\s*=\s*"([^"]*)"\s*(?:#.*)?$/,
    );
    if (valueMatch) {
      values[valueMatch[1]] = valueMatch[2];
    }
  }

  return values;
}

function assertTempoEnvSynced(taskDir) {
  const taskConfigPath = path.join(taskDir, "task.toml");
  const environmentEnv = readStringTable(taskConfigPath, "environment.env");
  const verifierEnv = readStringTable(taskConfigPath, "verifier.env");
  const keys = new Set([
    ...Object.keys(environmentEnv).filter((key) => key.startsWith("TEMPO_")),
    ...Object.keys(verifierEnv).filter((key) => key.startsWith("TEMPO_")),
  ]);
  const mismatches = [];

  for (const key of keys) {
    if (environmentEnv[key] !== verifierEnv[key]) {
      mismatches.push(
        `${key}: environment=${environmentEnv[key] ?? "<missing>"} verifier=${verifierEnv[key] ?? "<missing>"}`,
      );
    }
  }

  if (mismatches.length > 0) {
    throw new Error(
      `Tempo bench env mismatch in ${taskConfigPath}\n${mismatches.join("\n")}`,
    );
  }
}

function readTaskCaseId(taskDir) {
  const taskConfigPath = path.join(taskDir, "task.toml");
  return readStringTable(taskConfigPath, "verifier.env").TEMPO_BENCH_CASE;
}

function taskUsesTempoDocsMcp(taskDir) {
  const taskConfigPath = path.join(taskDir, "task.toml");
  const composePath = path.join(taskDir, "environment/docker-compose.yaml");
  const taskConfig = fs.existsSync(taskConfigPath) ? fs.readFileSync(taskConfigPath, "utf8") : "";
  const compose = fs.existsSync(composePath) ? fs.readFileSync(composePath, "utf8") : "";

  return taskConfig.includes("tempo-docs-mcp") || compose.includes("tempo-docs-mcp");
}

function taskDirs() {
  return fs
    .readdirSync(tasksDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(tasksDir, entry.name))
    .filter((dir) => fs.existsSync(path.join(dir, "task.toml")));
}

const tasks = taskDirs();

for (const taskDir of tasks) {
  assertTempoEnvSynced(taskDir);
  const caseId = readTaskCaseId(taskDir);
  if (!caseId) {
    throw new Error(`TEMPO_BENCH_CASE is missing in ${path.join(taskDir, "task.toml")}`);
  }

  copyVerifier(
    path.join(root, "shared/verifier"),
    path.join(taskDir, "tests/tempo-bench-verifier"),
    caseId,
  );
  syncRewardKit(taskDir);
  removePath(path.join(taskDir, "tests/check.py"));
  copyFile(
    path.join(root, "shared/rewardkit/test.sh"),
    path.join(taskDir, "tests/test.sh"),
  );
  fs.chmodSync(path.join(taskDir, "tests/test.sh"), 0o755);

  copyFile(
    path.join(root, "shared/docker/main-node/Dockerfile"),
    path.join(taskDir, "environment/Dockerfile"),
  );

  const localnetDir = path.join(taskDir, "environment/tempo-localnet");
  if (fs.existsSync(localnetDir)) {
    linkDir(path.join(root, "shared/docker/tempo-localnet"), localnetDir);
  }

  if (taskUsesTempoDocsMcp(taskDir)) {
    linkFile(
      path.join(root, "shared/docker/compose/tempo-localnet-docs-mcp.yaml"),
      path.join(taskDir, "environment/docker-compose.yaml"),
    );
    linkDir(
      path.join(root, "shared/mcp/tempo-docs"),
      path.join(taskDir, "environment/tempo-docs-mcp"),
    );
  } else {
    linkFile(
      path.join(root, "shared/docker/compose/tempo-localnet.yaml"),
      path.join(taskDir, "environment/docker-compose.yaml"),
    );
  }
}

console.log(
  `Synced verifier and linked localnet assets into ${tasks.length} task(s).`,
);
