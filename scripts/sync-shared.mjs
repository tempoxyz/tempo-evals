#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const tasksDir = path.join(root, "tasks");

function copyDir(source, destination) {
  fs.rmSync(destination, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.cpSync(source, destination, {
    recursive: true,
    filter: (sourcePath) =>
      !sourcePath.includes("node_modules") && !sourcePath.endsWith("package-lock.json"),
  });
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

  copyDir(
    path.join(root, "shared/verifier"),
    path.join(taskDir, "tests/tempo-bench-verifier"),
  );

  const localnetDir = path.join(taskDir, "environment/tempo-localnet");
  if (fs.existsSync(localnetDir)) {
    copyDir(path.join(root, "shared/docker/tempo-localnet"), localnetDir);
  }

  if (taskUsesTempoDocsMcp(taskDir)) {
    copyDir(
      path.join(root, "shared/mcp/tempo-docs"),
      path.join(taskDir, "environment/tempo-docs-mcp"),
    );
  }
}

console.log(
  `Synced shared verifier/localnet assets into ${tasks.length} task(s).`,
);
