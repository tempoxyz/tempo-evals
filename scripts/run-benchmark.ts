#!/usr/bin/env node
// Benchmark entrypoint for local Docker and Daytona jobs. Keep tracked task
// assets symlinked in tasks/tempo. Daytona runs create a temporary dereferenced
// task tree under .cache/harbor-daytona/<job>/tasks/tempo and rewrites the
// Harbor config to use it. Do not commit that staged tree or copy its files
// back into tasks/.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

type DocsLock = {
  schemaVersion: number;
  repo: string;
  sha: string;
};

type Variant = {
  config?: string;
  prefix: string;
  path?: string;
  defaultAgent?: string;
  defaultModel?: string;
  needsAgentAuth?: boolean;
  needsDaytonaAuth?: boolean;
};

type Options = {
  envFile?: string;
  help?: boolean;
  jobName?: string;
  concurrency?: string;
  agentConcurrency?: string;
  maxRetries?: string;
  agent?: string;
  model?: string;
  taskFilter?: string;
  nTasks?: string;
  tasks?: string;
  sync: boolean;
};

const variants: Record<string, Variant> = {
  "local-oracle": {
    config: "config/job.local.oracle.yaml",
    prefix: "tempo-bench-oracle-local",
  },
  "local-agent": {
    config: "config/job.local.agent.yaml",
    prefix: "tempo-bench-agents-local",
    needsAgentAuth: true,
  },
  "local-agent-dev": {
    config: "config/job.local.agent.dev.yaml",
    prefix: "tempo-bench-agents-dev-local",
    needsAgentAuth: true,
  },
  model: {
    path: "tasks/tempo",
    prefix: "tempo-bench-model-local",
    defaultAgent: "claude-code",
    defaultModel: "haiku",
    needsAgentAuth: true,
  },
  "daytona-oracle": {
    config: "config/job.daytona.oracle.yaml",
    prefix: "tempo-bench-oracle-daytona",
    needsDaytonaAuth: true,
  },
  "daytona-agent": {
    config: "config/job.daytona.agent.yaml",
    prefix: "tempo-bench-agents-daytona",
    needsAgentAuth: true,
    needsDaytonaAuth: true,
  },
  "daytona-agent-dev": {
    config: "config/job.daytona.agent.dev.yaml",
    prefix: "tempo-bench-agents-daytona-dev",
    needsAgentAuth: true,
    needsDaytonaAuth: true,
  },
};

function usage() {
  console.log(`Usage: npm run <script> -- [options]

Direct: node scripts/run-benchmark.ts <variant> [options]

Variants:
  local-oracle       Oracle validation on local Docker
  local-agent        Full Claude Code matrix on local Docker
  local-agent-dev    One-attempt Claude Code smoke run on local Docker
  model              One local harness/model run over tasks
  daytona-oracle     Oracle validation on Daytona
  daytona-agent      Full Claude Code matrix on Daytona
  daytona-agent-dev  One-attempt Claude Code smoke run on Daytona
  sync               Sync generated task assets only
  dataset            Sync generated task assets and Harbor dataset digests
  check-dataset      Verify dataset digests are fresh
  check-generated    Verify sync leaves no generated diff
  clean-jobs         Remove local Harbor job outputs
  clean              Remove local Harbor job outputs and Daytona staging cache

Options:
  --env-file PATH          Load env file for Harbor and preflight checks (default: .env when present)
  --job-name NAME          Override generated job name
  --concurrency N         Override n_concurrent_trials
  --agent-concurrency N   Override per-agent n_concurrent
  --max-retries N         Retry transient trial/setup failures (default: 2 for Daytona runs)
  --agent NAME            Agent for the model variant (default: claude-code)
  --model NAME            Model for the model variant (default: haiku)
  --task-filter GLOB      Include matching task names for model and Daytona config variants
  --n-tasks N             Limit task count for the model variant
  --tasks PATH            Task dataset path for dataset/model variants (default: tasks/tempo)
  --no-sync               Skip task asset and dataset sync before running Harbor
`);
}

function readOptionValue(argv: string[], index: number, option: string): string {
  const value = argv[index + 1];
  if (!value || value.startsWith("--")) {
    throw new Error(`Missing value for ${option}`);
  }
  return value;
}

function readPositiveInteger(value: string, option: string): string {
  if (!/^[1-9][0-9]*$/.test(value)) {
    throw new Error(`${option} must be a positive integer`);
  }
  return value;
}

function parseArgs(argv: string[]): { variant?: string; options: Options } {
  if (argv.length === 1 && (argv[0] === "--help" || argv[0] === "-h")) {
    return { options: { help: true, sync: true } };
  }

  const [variant, ...rest] = argv;
  const options: Options = {
    envFile: fs.existsSync(".env") ? ".env" : undefined,
    sync: true,
  };

  for (let i = 0; i < rest.length; i += 1) {
    const arg = rest[i];
    if (arg === "--help" || arg === "-h") {
      options.help = true;
    } else if (arg === "--no-sync") {
      options.sync = false;
    } else if (arg === "--env-file") {
      options.envFile = readOptionValue(rest, i, arg);
      i += 1;
    } else if (arg === "--job-name") {
      options.jobName = readOptionValue(rest, i, arg);
      i += 1;
    } else if (arg === "--concurrency") {
      options.concurrency = readPositiveInteger(readOptionValue(rest, i, arg), arg);
      i += 1;
    } else if (arg === "--agent-concurrency") {
      options.agentConcurrency = readPositiveInteger(readOptionValue(rest, i, arg), arg);
      i += 1;
    } else if (arg === "--max-retries") {
      options.maxRetries = readPositiveInteger(readOptionValue(rest, i, arg), arg);
      i += 1;
    } else if (arg === "--agent") {
      options.agent = readOptionValue(rest, i, arg);
      i += 1;
    } else if (arg === "--model") {
      options.model = readOptionValue(rest, i, arg);
      i += 1;
    } else if (arg === "--task-filter") {
      options.taskFilter = readOptionValue(rest, i, arg);
      i += 1;
    } else if (arg === "--n-tasks") {
      options.nTasks = readPositiveInteger(readOptionValue(rest, i, arg), arg);
      i += 1;
    } else if (arg === "--tasks") {
      options.tasks = readOptionValue(rest, i, arg);
      i += 1;
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }

  return { variant, options };
}

function loadEnvFile(filePath?: string) {
  if (!filePath) return;
  if (!fs.existsSync(filePath)) {
    throw new Error(`Env file not found: ${filePath}`);
  }
  for (const line of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) continue;
    const [, key, rawValue] = match;
    const value = rawValue.replace(/^['"]|['"]$/g, "");
    if (process.env[key] === undefined) {
      process.env[key] = value;
    }
  }
}

function timestamp() {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return [
    now.getFullYear(),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    "-",
    pad(now.getHours()),
    pad(now.getMinutes()),
    pad(now.getSeconds()),
  ].join("");
}

function run(command: string, args: string[]) {
  const result = spawnSync(command, args, {
    env: process.env,
    stdio: "inherit",
  });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status ?? 1);
}

function readDocsLock(): DocsLock {
  const lockPath = path.join("config", "tempo-docs.lock.json");
  const lock = JSON.parse(fs.readFileSync(lockPath, "utf8")) as DocsLock;
  if (lock.schemaVersion !== 1 || !lock.repo || !lock.sha) {
    throw new Error(`Invalid Tempo docs lock: ${lockPath}`);
  }
  return lock;
}

function docsBundlePath(): string {
  const lock = readDocsLock();
  return path.resolve(".cache", "tempo-docs", lock.sha, "public");
}

function ensureDocsBundle(): string {
  run("node", ["scripts/prepare-docs-bundle.mjs"]);
  const bundlePath = docsBundlePath();
  if (!fs.existsSync(path.join(bundlePath, "developers", "llms.txt"))) {
    throw new Error(`Pinned Tempo docs bundle was not created at ${bundlePath}`);
  }
  return bundlePath;
}

function requireAny(names: string[], message: string) {
  if (!names.some((name) => process.env[name])) {
    throw new Error(message);
  }
}

function preflight(variant: Variant) {
  if (variant.needsAgentAuth) {
    requireAny(
      ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"],
      "Missing Claude Code auth: set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN.",
    );
    requireAny(
      ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"],
      "Missing verifier judge auth: set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN.",
    );
  }
  if (
    variant.needsDaytonaAuth &&
    !process.env.DAYTONA_API_KEY &&
    !(process.env.DAYTONA_JWT_TOKEN && process.env.DAYTONA_ORGANIZATION_ID)
  ) {
    throw new Error(
      "Missing Daytona auth: set DAYTONA_API_KEY, or both DAYTONA_JWT_TOKEN and DAYTONA_ORGANIZATION_ID.",
    );
  }
}

function taskPath(options: Options): string {
  return options.tasks ?? "tasks/tempo";
}

function syncDataset(options: Options) {
  run("node", ["scripts/sync-shared.mjs"]);
  run("uv", ["run", "harbor", "sync", taskPath(options)]);
}

function applyTaskFilter(config: string, taskFilter?: string): string {
  if (!taskFilter) return config;
  const filters = taskFilter.startsWith("tempo/")
    ? [taskFilter, taskFilter.slice("tempo/".length)]
    : [taskFilter];
  const filtered = config.replace(
    /(^\s+task_names:\n)(?:^\s+-\s+.*\n)+/m,
    `$1${filters.map((filter) => `      - ${JSON.stringify(filter)}\n`).join("")}`,
  );
  if (filtered === config) {
    throw new Error("Could not apply task filter to config");
  }
  return filtered;
}

function stageDaytonaConfig(
  configPath: string,
  runId: string,
  docsBundle: string,
  taskFilter?: string,
): string {
  const stagingRoot = path.join(".cache", "harbor-daytona", runId);
  const sourceTasks = "tasks/tempo";
  const stagedTasks = path.join(stagingRoot, "tasks", "tempo");
  const stagedConfig = path.join(stagingRoot, path.basename(configPath));

  fs.rmSync(stagingRoot, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(stagedTasks), { recursive: true });
  fs.cpSync(sourceTasks, stagedTasks, {
    recursive: true,
    dereference: true,
    filter: (sourcePath) =>
      !sourcePath.includes(`${path.sep}node_modules${path.sep}`) &&
      !sourcePath.endsWith(`${path.sep}package-lock.json`),
  });
  for (const entry of fs.readdirSync(stagedTasks, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const taskDir = path.join(stagedTasks, entry.name);
    const taskConfigPath = path.join(taskDir, "task.toml");
    if (!fs.existsSync(taskConfigPath)) continue;
    const taskConfig = fs.readFileSync(taskConfigPath, "utf8");
    if (!taskConfig.includes("TEMPO_DOCS_URL")) continue;
    fs.cpSync(docsBundle, path.join(taskDir, "environment", "tempo-docs-bundle"), {
      recursive: true,
    });
  }

  const config = fs.readFileSync(configPath, "utf8");
  const redirected = applyTaskFilter(config, taskFilter).replace(
    /(^\s*-\s*path:\s*)tasks\/tempo\s*$/m,
    `$1${JSON.stringify(stagedTasks)}`,
  );
  if (redirected === config) {
    throw new Error(`Could not redirect dataset path in ${configPath}`);
  }
  fs.writeFileSync(stagedConfig, redirected);
  return stagedConfig;
}

function stageFilteredConfig(configPath: string, runId: string, taskFilter?: string): string {
  if (!taskFilter) return configPath;
  const stagingRoot = path.join(".cache", "harbor-config", runId);
  const stagedConfig = path.join(stagingRoot, path.basename(configPath));

  fs.rmSync(stagingRoot, { recursive: true, force: true });
  fs.mkdirSync(stagingRoot, { recursive: true });
  fs.writeFileSync(stagedConfig, applyTaskFilter(fs.readFileSync(configPath, "utf8"), taskFilter));
  return stagedConfig;
}

try {
  const { variant: variantName, options } = parseArgs(process.argv.slice(2));
  if (options.help || !variantName) {
    usage();
    process.exit(options.help ? 0 : 1);
  }
  if (variantName === "sync") {
    run("node", ["scripts/sync-shared.mjs"]);
    process.exit(0);
  }
  if (variantName === "dataset") {
    syncDataset(options);
    process.exit(0);
  }
  if (variantName === "check-dataset") {
    syncDataset(options);
    run("git", ["diff", "--exit-code", `${taskPath(options)}/dataset.toml`]);
    process.exit(0);
  }
  if (variantName === "check-generated") {
    syncDataset(options);
    run("git", ["diff", "--exit-code"]);
    process.exit(0);
  }
  if (variantName === "clean-jobs") {
    fs.rmSync("jobs", { recursive: true, force: true });
    fs.mkdirSync("jobs", { recursive: true });
    process.exit(0);
  }
  if (variantName === "clean") {
    fs.rmSync("jobs", { recursive: true, force: true });
    fs.rmSync(path.join(".cache", "harbor-daytona"), { recursive: true, force: true });
    fs.rmSync(path.join(".cache", "harbor-config"), { recursive: true, force: true });
    fs.mkdirSync("jobs", { recursive: true });
    process.exit(0);
  }

  const variant = variants[variantName];
  if (!variant) {
    usage();
    throw new Error(`Unknown variant: ${variantName}`);
  }

  loadEnvFile(options.envFile);
  preflight(variant);
  if (options.sync) syncDataset(options);
  const docsBundle = ensureDocsBundle();

  const runId = options.jobName ?? `${variant.prefix}-${timestamp()}`;
  const args = ["run", "harbor", "run"];
  if (variant.config) {
    const config = variant.needsDaytonaAuth
      ? stageDaytonaConfig(variant.config, runId, docsBundle, options.taskFilter)
      : stageFilteredConfig(variant.config, runId, options.taskFilter);
    args.push("-c", config);
  } else {
    args.push("--path", options.tasks ?? variant.path ?? "tasks/tempo");
    args.push("--agent", options.agent ?? variant.defaultAgent ?? "claude-code");
    const model = options.model ?? variant.defaultModel;
    if (model) args.push("--model", model);
    if (options.taskFilter) args.push("--include-task-name", options.taskFilter);
    if (options.nTasks) args.push("--n-tasks", options.nTasks);
  }
  if (options.envFile) args.push("--env-file", options.envFile);
  args.push("--job-name", runId);
  if (options.concurrency) args.push("--n-concurrent", options.concurrency);
  if (options.agentConcurrency) {
    args.push("--n-concurrent-agents", options.agentConcurrency);
  }
  const maxRetries = options.maxRetries ?? (variant.needsDaytonaAuth ? "2" : undefined);
  if (maxRetries) args.push("--max-retries", maxRetries);
  process.env.TEMPO_DOCS_BUNDLE_PATH = variant.needsDaytonaAuth ? "" : docsBundle;
  args.push("-y");
  run("uv", args);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
