#!/usr/bin/env node
// Daytona benchmark entrypoint. Keep tracked task assets symlinked in tasks/.
// For Daytona runs, this script creates a temporary dereferenced task tree under
// .cache/harbor-daytona/<job>/tasks and rewrites the Harbor config to use it.
// Do not commit that staged tree or copy its files back into tasks/.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

type Variant = {
  config: string;
  prefix: string;
  needsAgentAuth?: boolean;
  needsDaytonaAuth?: boolean;
};

type Options = {
  envFile?: string;
  help?: boolean;
  jobName?: string;
  concurrency?: string;
  agentConcurrency?: string;
  sync: boolean;
};

const variants: Record<string, Variant> = {
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
  daytona-oracle     Oracle validation on Daytona
  daytona-agent      Full Claude Code matrix on Daytona
  daytona-agent-dev  One-attempt Claude Code smoke run on Daytona
  sync               Sync generated task assets only
  dataset            Sync generated task assets and Harbor dataset digests

Options:
  --env-file PATH          Load env file for Harbor and preflight checks (default: .env when present)
  --job-name NAME          Override generated job name
  --concurrency N         Override n_concurrent_trials
  --agent-concurrency N   Override per-agent n_concurrent
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
  const pad = (value) => String(value).padStart(2, "0");
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

function requireAny(names: string[], message: string) {
  if (!names.some((name) => process.env[name])) {
    throw new Error(message);
  }
}

function preflight(variant: Variant) {
  if (process.env.CLAUDE_FORCE_OAUTH === "") {
    throw new Error("CLAUDE_FORCE_OAUTH is set but empty. Set it to 1/true or unset it.");
  }
  if (variant.needsAgentAuth) {
    requireAny(
      ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"],
      "Missing Claude Code auth: set ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or CLAUDE_CODE_OAUTH_TOKEN.",
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

function syncDataset() {
  run("node", ["scripts/sync-shared.mjs"]);
  run("uv", ["run", "harbor", "sync", "tasks"]);
}

function stageDaytonaConfig(configPath: string, runId: string): string {
  const stagingRoot = path.join(".cache", "harbor-daytona", runId);
  const stagedTasks = path.join(stagingRoot, "tasks");
  const stagedConfig = path.join(stagingRoot, path.basename(configPath));

  fs.rmSync(stagingRoot, { recursive: true, force: true });
  fs.mkdirSync(stagingRoot, { recursive: true });
  fs.cpSync("tasks", stagedTasks, {
    recursive: true,
    dereference: true,
    filter: (sourcePath) =>
      !sourcePath.includes(`${path.sep}node_modules${path.sep}`) &&
      !sourcePath.endsWith(`${path.sep}package-lock.json`),
  });

  const config = fs.readFileSync(configPath, "utf8");
  const redirected = config.replace(
    /(^\s*-\s*path:\s*)tasks\s*$/m,
    `$1${JSON.stringify(stagedTasks)}`,
  );
  if (redirected === config) {
    throw new Error(`Could not redirect dataset path in ${configPath}`);
  }
  fs.writeFileSync(stagedConfig, redirected);
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
    syncDataset();
    process.exit(0);
  }

  const variant = variants[variantName];
  if (!variant) {
    usage();
    throw new Error(`Unknown variant: ${variantName}`);
  }

  loadEnvFile(options.envFile);
  preflight(variant);
  if (options.sync) syncDataset();

  const runId = options.jobName ?? `${variant.prefix}-${timestamp()}`;
  const config = variant.needsDaytonaAuth
    ? stageDaytonaConfig(variant.config, runId)
    : variant.config;

  const args = ["run", "harbor", "run", "-c", config];
  if (options.envFile) args.push("--env-file", options.envFile);
  args.push("--job-name", runId);
  if (options.concurrency) args.push("--n-concurrent", options.concurrency);
  if (options.agentConcurrency) {
    args.push("--n-concurrent-agents", options.agentConcurrency);
  }
  args.push("-y");
  run("uv", args);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
