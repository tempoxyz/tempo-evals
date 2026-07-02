#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const tasksDir = path.join(root, "tasks");
const tempoDocsUrl = "https://docs.tempo.xyz/";
const tempoMcpUrl = "https://mcp.tempo.xyz";
const defaultTurnCutoffs = "20=1.0,40=0.8,60=0.5,80=0.2,*=0.0";
const defaultTokenCutoffs = "250000=1.0,500000=0.8,1000000=0.5,1500000=0.2,*=0.0";
const sourceTaskSlugs = [
  "transfer-with-memo",
  "transfer-with-memo-fee-payer",
  "create-access-key-transfer",
  "access-key-spending-limit",
  "set-fee-token",
  "create-stablecoin-with-policy",
  "receive-policy-bounced-transfer",
  "faucet-funded-transfer",
  "stablecoin-dex-swap",
  "multiparty-batch-transfer",
];
const profiles = [
  {
    id: "docs",
    suffix: "-docs",
    label: "docs",
  },
  {
    id: "mcp",
    suffix: "-mcp",
    label: "MCP",
  },
];
const executionConstraints = `## Execution Constraints

- \`TEMPO_RPC_URL\` is already set to the Tempo localnet RPC endpoint (\`http://tempo-localnet:8545\`).
- Use that localnet RPC endpoint for all build, run, and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local build/run checks must use the provided environment variables.
`;

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

function copyGeneratedTask(source, destination) {
  removePath(destination);
  fs.mkdirSync(path.dirname(destination), { recursive: true });
  fs.cpSync(source, destination, {
    recursive: true,
    filter: (sourcePath) => {
      const relativePath = path.relative(source, sourcePath);
      if (sourcePath.includes("node_modules") || sourcePath.endsWith("package-lock.json")) {
        return false;
      }
      return ![
        "environment/Dockerfile",
        "environment/docker-compose.yaml",
        "environment/tempo-localnet",
        "environment/tempo-docs-mcp",
        "environment/rewardkit-package",
        "tests/tempo-bench-verifier",
        "tests/e2e/verify-tempo.sh",
        "tests/correctness/verify-tempo.sh",
        "tests/quality",
        "tests/test.sh",
      ].some((excludedPath) =>
        relativePath === excludedPath || relativePath.startsWith(`${excludedPath}${path.sep}`),
      );
    },
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

function replaceTomlString(content, key, value) {
  const encodedValue = JSON.stringify(value);
  return content.replace(
    new RegExp(`(^\\s*${key}\\s*=\\s*)"[^"]*"`, "m"),
    `$1${encodedValue}`,
  );
}

function appendTomlStringToTable(content, tableName, key, value) {
  const tableStart = content.indexOf(`[${tableName}]`);
  if (tableStart === -1) {
    throw new Error(`Missing [${tableName}] table`);
  }

  const nextTableStart = content.indexOf("\n[", tableStart + tableName.length + 2);
  const end = nextTableStart === -1 ? content.length : nextTableStart + 1;
  const table = content.slice(tableStart, end);
  const keyPattern = new RegExp(`^\\s*${key}\\s*=`, "m");
  const nextContent = table.match(keyPattern)
    ? content.replace(
        new RegExp(`(^\\s*${key}\\s*=\\s*)"[^"]*"`, "m"),
        `$1${JSON.stringify(value)}`,
      )
    : `${content.slice(0, end).replace(/\s*$/, "")}\n${key} = ${JSON.stringify(value)}\n${content.slice(end)}`;

  return nextContent;
}

function ensureTomlStringInTable(content, tableName, key, value) {
  const tableStart = content.indexOf(`[${tableName}]`);
  if (tableStart === -1) {
    throw new Error(`Missing [${tableName}] table`);
  }

  const nextTableStart = content.indexOf("\n[", tableStart + tableName.length + 2);
  const end = nextTableStart === -1 ? content.length : nextTableStart + 1;
  const table = content.slice(tableStart, end);
  if (new RegExp(`^\\s*${key}\\s*=`, "m").test(table)) {
    return content;
  }
  return `${content.slice(0, end).replace(/\s*$/, "")}\n${key} = ${JSON.stringify(value)}\n${content.slice(end)}`;
}

function removeTomlKeyFromTable(content, tableName, key) {
  const tableStart = content.indexOf(`[${tableName}]`);
  if (tableStart === -1) return content;

  const nextTableStart = content.indexOf("\n[", tableStart + tableName.length + 2);
  const end = nextTableStart === -1 ? content.length : nextTableStart + 1;
  const before = content.slice(0, tableStart);
  const table = content
    .slice(tableStart, end)
    .split(/\r?\n/)
    .filter((line) => !new RegExp(`^\\s*${key}\\s*=`).test(line))
    .join("\n");
  return `${before}${table}${content.slice(end)}`;
}

function clearEnvironmentNetworkPolicy(content) {
  content = removeTomlKeyFromTable(content, "environment", "network_mode");
  return removeTomlKeyFromTable(content, "environment", "allowed_hosts");
}

function removeEnvironmentMcpServers(content) {
  return content.replace(
    /\n\[\[environment\.mcp_servers\]\]\n(?:[^\n]*\n)*?(?=\n(?:\[|\[\[)|$)/g,
    "\n",
  );
}

function addTempoMcpServer(content) {
  const block = `\n[[environment.mcp_servers]]\nname = "tempo"\ntransport = "streamable-http"\nurl = "${tempoMcpUrl}"\n`;
  const environmentEnvStart = content.indexOf("\n[environment.env]");
  if (environmentEnvStart === -1) {
    return `${content.replace(/\s*$/, "")}${block}\n`;
  }
  return `${content.slice(0, environmentEnvStart).replace(/\s*$/, "")}${block}${content.slice(environmentEnvStart)}`;
}

function replaceOrAddMetadataProfile(content, profileId) {
  const tableStart = content.indexOf("[metadata]");
  if (tableStart === -1) return content;

  const nextTableStart = content.indexOf("\n[", tableStart + "[metadata]".length);
  const end = nextTableStart === -1 ? content.length : nextTableStart + 1;
  const table = content.slice(tableStart, end);
  if (/^\s*profile\s*=/m.test(table)) {
    return content.replace(/(^\s*profile\s*=\s*)"[^"]*"/m, `$1${JSON.stringify(profileId)}`);
  }
  return `${content.slice(0, end).replace(/\s*$/, "")}\nprofile = ${JSON.stringify(profileId)}\n${content.slice(end)}`;
}

function removeMetadataProfile(content) {
  return removeTomlKeyFromTable(content, "metadata", "profile");
}

function addKeyword(content, keyword) {
  return content.replace(/keywords\s*=\s*\[([^\]]*)\]/, (match, values) => {
    if (values.includes(JSON.stringify(keyword))) return match;
    const trimmed = values.trim();
    return `keywords = [${trimmed ? `${trimmed}, ` : " "}${JSON.stringify(keyword)}]`;
  });
}

function updateTaskToml(taskDir, sourceSlug, profile) {
  const taskConfigPath = path.join(taskDir, "task.toml");
  const taskName = `tempo/${sourceSlug}${profile.suffix}`;
  let content = fs.readFileSync(taskConfigPath, "utf8");

  content = replaceTomlString(content, "name", taskName);
  content = replaceTomlString(
    content,
    "description",
    `${content.match(/description\s*=\s*"([^"]*)"/)?.[1] ?? taskName} (${profile.label} profile).`,
  );
  content = removeEnvironmentMcpServers(content);
  content = removeTomlKeyFromTable(content, "environment.env", "TEMPO_DOCS_URL");
  content = clearEnvironmentNetworkPolicy(content);

  content = replaceOrAddMetadataProfile(content, profile.id);
  content = addKeyword(content, profile.id);

  if (profile.id === "docs") {
    content = appendTomlStringToTable(content, "environment.env", "TEMPO_DOCS_URL", tempoDocsUrl);
  } else if (profile.id === "mcp") {
    content = addTempoMcpServer(content);
  }

  writeFile(taskConfigPath, `${content.replace(/\s*$/, "")}\n`);
}

function appendProfileInstruction(taskDir, profile) {
  const instructionPath = path.join(taskDir, "instruction.md");
  let content = fs.readFileSync(instructionPath, "utf8").replace(
    /\nTempo integration docs are available through the configured MCP server named[\s\S]*?Use it if your agent runtime exposes MCP tools\.\n/,
    "\n",
  );
  content = content.replace(/\n## Tempo Access Profile[\s\S]*?(?=\n## |\nRequirements:|$)/, "\n");
  content = content.replace(/\n## Execution Constraints[\s\S]*?(?=\n## |\nRequirements:|$)/, "\n");

  if (profile.id === "docs") {
    content = content.replace(
      "\nRequirements:",
      `\n## Tempo Access Profile\n\nTempo docs are available at ${tempoDocsUrl} and through the \`TEMPO_DOCS_URL\` environment variable. You may use WebSearch/WebFetch for Tempo docs; prefer docs from docs.tempo.xyz and do not use public RPC endpoints.\n\nRequirements:`,
    );
  } else if (profile.id === "mcp") {
    content = content.replace(
      "\nRequirements:",
      "\n## Tempo Access Profile\n\nThe official Tempo MCP server is configured as `tempo`. Use it if your agent runtime exposes MCP tools; do not use WebSearch, WebFetch, or public RPC endpoints.\n\nRequirements:",
    );
  }

  content = content.replace("\nRequirements:", `\n${executionConstraints}\nRequirements:`);

  writeFile(instructionPath, `${content.replace(/\s*$/, "")}\n`);
}

function taskCriteriaPath(taskDir) {
  for (const relativePath of [
    "tests/correctness/criteria.py",
    "tests/criteria/check.py",
  ]) {
    const absolutePath = path.join(taskDir, relativePath);
    if (fs.existsSync(absolutePath)) return absolutePath;
  }
  throw new Error(`Missing task-local criteria checks in ${taskDir}`);
}

function updateProfileCriteria(taskDir, profile) {
  const criteriaPath = taskCriteriaPath(taskDir);
  let content = fs.readFileSync(criteriaPath, "utf8");
  content = content.replace(
    /\nrk\.tempo_trajectory_matches\([\s\S]*?\n\)\n/g,
    "\n",
  );

  if (profile.id === "docs") {
    content += `
rk.tempo_trajectory_matches(
    r"docs\\.tempo\\.xyz|TEMPO_DOCS_URL|Tempo docs|documentation",
)
`;
  } else if (profile.id === "mcp") {
    content += `
rk.tempo_trajectory_matches(
    r"tempo|mcp|docs|documentation|search",
)
`;
  }

  writeFile(criteriaPath, `${content.replace(/\s*$/, "")}\n`);
}

function materializeTaskMatrix() {
  const generatedSlugs = new Set();
  for (const sourceSlug of sourceTaskSlugs) {
    const sourceDir = path.join(tasksDir, sourceSlug);
    if (!fs.existsSync(path.join(sourceDir, "task.toml"))) {
      throw new Error(`Missing source task: ${sourceDir}`);
    }

    for (const profile of profiles) {
      const slug = `${sourceSlug}${profile.suffix}`;
      const taskDir = path.join(tasksDir, slug);
      copyGeneratedTask(sourceDir, taskDir);
      generatedSlugs.add(slug);
      updateTaskToml(taskDir, sourceSlug, profile);
      appendProfileInstruction(taskDir, profile);
      updateProfileCriteria(taskDir, profile);
    }
  }

  removePath(path.join(tasksDir, "transfer-with-memo-docs-mcp"));
  for (const entry of fs.readdirSync(tasksDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const slug = entry.name;
    const isGeneratedProfile =
      slug.endsWith("-docs") ||
      slug.endsWith("-mcp") ||
      slug.endsWith("-docs-url") ||
      slug.endsWith("-tempo-mcp") ||
      slug.endsWith("-docs-mcp");
    if (isGeneratedProfile && !generatedSlugs.has(slug)) {
      removePath(path.join(tasksDir, slug));
    }
  }
}

function readDatasetDigests() {
  const datasetPath = path.join(tasksDir, "dataset.toml");
  if (!fs.existsSync(datasetPath)) return new Map();

  const digests = new Map();
  let currentName = null;
  for (const line of fs.readFileSync(datasetPath, "utf8").split(/\r?\n/)) {
    const nameMatch = line.match(/^\s*name\s*=\s*"([^"]+)"\s*$/);
    if (nameMatch) {
      currentName = nameMatch[1];
      continue;
    }
    const digestMatch = line.match(/^\s*digest\s*=\s*"([^"]+)"\s*$/);
    if (digestMatch && currentName) {
      digests.set(currentName, digestMatch[1]);
      currentName = null;
    }
  }
  return digests;
}

function matrixTaskNames() {
  return sourceTaskSlugs.flatMap((sourceSlug) =>
    profiles.map((profile) => `tempo/${sourceSlug}${profile.suffix}`),
  );
}

function writeDatasetManifest() {
  const digests = readDatasetDigests();
  const placeholderDigest =
    "sha256:0000000000000000000000000000000000000000000000000000000000000000";
  const taskEntries = matrixTaskNames()
    .map(
      (name) => `[[tasks]]
name = ${JSON.stringify(name)}
digest = ${JSON.stringify(digests.get(name) ?? placeholderDigest)}
`,
    )
    .join("\n");

  writeFile(
    path.join(tasksDir, "dataset.toml"),
    `# Dataset manifest for tempo/tempo-bench
# Generated by scripts/sync-shared.mjs. Run \`harbor sync tasks\` to refresh digests.

[dataset]
name = "tempo/tempo-bench"
description = "Tempo integration benchmark"
keywords = ["stablecoins", "docs", "tempo"]
[[dataset.authors]]
name = "Tempo"

${taskEntries}`,
  );
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
  if (!fs.existsSync(path.join(taskDir, "tests/reward.toml"))) {
    throw new Error(`Missing task-local RewardKit file: ${path.join(taskDir, "tests/reward.toml")}`);
  }
  const criteriaCandidates = ["tests/correctness/criteria.py", "tests/criteria/check.py"];
  if (!criteriaCandidates.some((relativePath) => fs.existsSync(path.join(taskDir, relativePath)))) {
    throw new Error(`Missing task-local RewardKit file: ${criteriaCandidates.join(" or ")} in ${taskDir}`);
  }
}

function readFirstExisting(taskDir, relativePaths) {
  for (const relativePath of relativePaths) {
    const absolutePath = path.join(taskDir, relativePath);
    if (fs.existsSync(absolutePath)) {
      return fs.readFileSync(absolutePath, "utf8");
    }
  }
  throw new Error(`Missing required file in ${taskDir}: ${relativePaths.join(" or ")}`);
}

function syncRewardKit(taskDir) {
  assertTaskRewardKit(taskDir);
  const criteriaContent = readFirstExisting(taskDir, [
    "tests/correctness/criteria.py",
    "tests/criteria/check.py",
  ]).replaceAll("/tests/e2e/verify-tempo.sh", "/tests/correctness/verify-tempo.sh");

  removePath(path.join(taskDir, "tests/turns"));
  removePath(path.join(taskDir, "tests/tokens"));
  removePath(path.join(taskDir, "tests/reward"));
  removePath(path.join(taskDir, "tests/criteria"));
  removePath(path.join(taskDir, "tests/criteria.py"));
  removePath(path.join(taskDir, "tests/e2e"));
  removePath(path.join(taskDir, "tests/correctness"));
  removePath(path.join(taskDir, "tests/quality"));
  writeFile(
    path.join(taskDir, "tests/reward.toml"),
    `[[reward]]\nname = "reward"\naggregation = "weighted_mean"\n`,
  );
  writeFile(path.join(taskDir, "tests/correctness/criteria.py"), criteriaContent);
  copyDir(
    path.join(root, "shared/rewardkit/quality"),
    path.join(taskDir, "tests/quality"),
  );
  copyFile(
    path.join(root, "shared/rewardkit/verify-tempo.sh"),
    path.join(taskDir, "tests/correctness/verify-tempo.sh"),
  );
  fs.chmodSync(path.join(taskDir, "tests/correctness/verify-tempo.sh"), 0o755);
}

function ensureQualityEnv(taskDir) {
  const taskConfigPath = path.join(taskDir, "task.toml");
  let content = fs.readFileSync(taskConfigPath, "utf8");
  content = ensureTomlStringInTable(
    content,
    "environment.env",
    "TEMPO_BENCH_TURNS_SCORE_CUTOFFS",
    defaultTurnCutoffs,
  );
  content = ensureTomlStringInTable(
    content,
    "environment.env",
    "TEMPO_BENCH_TOKENS_SCORE_CUTOFFS",
    defaultTokenCutoffs,
  );
  writeFile(taskConfigPath, `${content.replace(/\s*$/, "")}\n`);
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

function readStringValue(filePath, dottedKey) {
  let currentTable = "";

  for (const line of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const tableMatch = line.match(/^\s*\[([^\]]+)\]\s*$/);
    if (tableMatch) {
      currentTable = tableMatch[1];
      continue;
    }

    const valueMatch = line.match(
      /^\s*([A-Za-z0-9_.]+)\s*=\s*"([^"]*)"\s*(?:#.*)?$/,
    );
    const fullKey =
      valueMatch && currentTable
        ? `${currentTable}.${valueMatch[1]}`
        : valueMatch?.[1];
    if (valueMatch && fullKey === dottedKey) {
      return valueMatch[2];
    }
  }

  return undefined;
}

function assertVerifierEnvAllowed(taskDir) {
  const taskConfigPath = path.join(taskDir, "task.toml");
  const verifierEnv = readStringTable(taskConfigPath, "verifier.env");
  const environmentMode = readStringValue(taskConfigPath, "verifier.environment_mode");

  if (environmentMode !== "separate" && Object.keys(verifierEnv).length > 0) {
    throw new Error(
      `[verifier.env] must be absent unless [verifier].environment_mode = "separate" in ${taskConfigPath}`,
    );
  }
}

function readTaskCaseId(taskDir) {
  const taskConfigPath = path.join(taskDir, "task.toml");
  return readStringTable(taskConfigPath, "environment.env").TEMPO_BENCH_CASE;
}

function taskUsesLocalTempoDocsMcp(taskDir) {
  const taskConfigPath = path.join(taskDir, "task.toml");
  const composePath = path.join(taskDir, "environment/docker-compose.yaml");
  const taskConfig = fs.existsSync(taskConfigPath) ? fs.readFileSync(taskConfigPath, "utf8") : "";
  const compose = fs.existsSync(composePath) ? fs.readFileSync(composePath, "utf8") : "";

  return taskConfig.includes("tempo-docs-mcp") || compose.includes("tempo-docs-mcp");
}

function assertComposeBuildContexts(taskDir) {
  const composePath = path.join(taskDir, "environment/docker-compose.yaml");
  const compose = fs.readFileSync(composePath, "utf8");
  const contextMatches = compose.matchAll(/^\s*context:\s*(.+?)\s*$/gm);
  for (const match of contextMatches) {
    const contextPath = match[1].replace(/^["']|["']$/g, "");
    const absoluteContextPath = path.resolve(path.dirname(composePath), contextPath);
    if (!fs.existsSync(absoluteContextPath)) {
      throw new Error(`Missing Docker Compose build context: ${absoluteContextPath}`);
    }
  }
}

function taskDirs() {
  return fs
    .readdirSync(tasksDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(tasksDir, entry.name))
    .filter((dir) => fs.existsSync(path.join(dir, "task.toml")));
}

materializeTaskMatrix();
writeDatasetManifest();
const tasks = taskDirs();

for (const taskDir of tasks) {
  ensureQualityEnv(taskDir);
  assertVerifierEnvAllowed(taskDir);
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
  copyDir(
    path.join(root, "shared/rewardkit-package"),
    path.join(taskDir, "environment/rewardkit-package"),
  );

  linkDir(
    path.join(root, "shared/docker/tempo-localnet"),
    path.join(taskDir, "environment/tempo-localnet"),
  );

  if (taskUsesLocalTempoDocsMcp(taskDir)) {
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

  assertComposeBuildContexts(taskDir);
}

console.log(
  `Synced verifier and linked localnet assets into ${tasks.length} task(s).`,
);
