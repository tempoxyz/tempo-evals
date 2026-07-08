#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Command } from "commander";
import { stringify } from "csv-stringify/sync";
import fg from "fast-glob";

type JsonObject = Record<string, unknown>;
type Numeric = number | "";

export type ExportOptions = {
  jobDir: string;
  runId?: string;
  outDir?: string;
};

export type TrialRow = {
  run_id: string;
  job_name: string;
  trial_name: string;
  task_name: string;
  task_family: string;
  profile: string;
  agent: string;
  model: string;
  attempt_index: number;
  reward: Numeric;
  passed: boolean;
  exception_type: string;
  exception_message: string;
  started_at: string;
  finished_at: string;
  duration_sec: Numeric;
  environment_setup_duration_sec: Numeric;
  agent_setup_duration_sec: Numeric;
  agent_execution_duration_sec: Numeric;
  verifier_duration_sec: Numeric;
  input_tokens: Numeric;
  cache_tokens: Numeric;
  output_tokens: Numeric;
  cost_usd: Numeric;
  task_checksum: string;
  git_sha: string;
  docs_lock_sha: string;
  result_path: string;
  rewards: Record<string, number>;
};

type SummaryRow = {
  run_id: string;
  job_name: string;
  model: string;
  agent: string;
  task_name: string;
  task_family: string;
  profile: string;
  n_trials: number;
  n_passed: number;
  pass_rate: number;
  n_errors: number;
  mean_reward: Numeric;
  input_tokens: number;
  cache_tokens: number;
  output_tokens: number;
  cost_usd: number;
};

type Metadata = {
  run_id?: string;
  git_sha?: string | null;
  docs_lock?: { sha?: string };
};

type ExportContext = {
  runId: string;
  jobName: string;
  gitSha: string;
  docsLockSha: string;
};

const PROFILES = ["base", "docs", "mcp"] as const;

const TRIAL_COLUMNS = [
  "run_id",
  "job_name",
  "trial_name",
  "task_name",
  "task_family",
  "profile",
  "agent",
  "model",
  "attempt_index",
  "reward",
  "passed",
  "exception_type",
  "exception_message",
  "started_at",
  "finished_at",
  "duration_sec",
  "environment_setup_duration_sec",
  "agent_setup_duration_sec",
  "agent_execution_duration_sec",
  "verifier_duration_sec",
  "input_tokens",
  "cache_tokens",
  "output_tokens",
  "cost_usd",
  "task_checksum",
  "git_sha",
  "docs_lock_sha",
  "result_path",
] as const;

const SUMMARY_COLUMNS = [
  "run_id",
  "job_name",
  "model",
  "agent",
  "task_name",
  "task_family",
  "profile",
  "n_trials",
  "n_passed",
  "pass_rate",
  "n_errors",
  "mean_reward",
  "input_tokens",
  "cache_tokens",
  "output_tokens",
  "cost_usd",
] as const;

function readJson<T extends JsonObject = JsonObject>(filePath: string): T | undefined {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8")) as T;
  } catch {
    return undefined;
  }
}

function readMetadata(jobDir: string): Metadata {
  return readJson<Metadata>(path.join(path.dirname(jobDir), "metadata.json")) ?? {};
}

function commandOutput(command: string, args: string[]): string {
  const result = spawnSync(command, args, { encoding: "utf8" });
  return result.status === 0 ? result.stdout.trim() : "";
}

function docsLockSha(): string {
  return readJson(path.join("config", "tempo-docs.lock.json"))?.sha?.toString() ?? "";
}

function defaultRunId(jobDir: string, metadata: Metadata): string {
  if (metadata.run_id) return metadata.run_id;
  return path.basename(jobDir) === "harbor-job"
    ? path.basename(path.dirname(jobDir))
    : path.basename(jobDir);
}

function defaultOutDir(jobDir: string): string {
  return path.basename(jobDir) === "harbor-job"
    ? path.join(path.dirname(jobDir), "exports")
    : path.join(jobDir, "exports");
}

function buildContext(jobDir: string, runId: string, metadata: Metadata): ExportContext {
  return {
    runId,
    jobName: path.basename(jobDir),
    gitSha: metadata.git_sha ?? commandOutput("git", ["rev-parse", "HEAD"]),
    docsLockSha: metadata.docs_lock?.sha ?? docsLockSha(),
  };
}

function resultFiles(root: string): string[] {
  return fg
    .sync("**/result.json", {
      absolute: true,
      cwd: root,
      ignore: ["**/exports/**"],
      onlyFiles: true,
    })
    .sort();
}

export function parseTaskName(taskName: string): { taskFamily: string; profile: string } {
  for (const profile of PROFILES) {
    const suffix = `-${profile}`;
    if (taskName.endsWith(suffix)) {
      return { taskFamily: taskName.slice(0, -suffix.length), profile };
    }
  }
  return { taskFamily: taskName, profile: "unknown" };
}

function asObject(value: unknown): JsonObject {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonObject)
    : {};
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function durationSec(timing: unknown): Numeric {
  const object = asObject(timing);
  const startedAt = asString(object.started_at);
  const finishedAt = asString(object.finished_at);
  if (!startedAt || !finishedAt) return "";

  const started = Date.parse(startedAt);
  const finished = Date.parse(finishedAt);
  if (!Number.isFinite(started) || !Number.isFinite(finished)) return "";
  return Math.max((finished - started) / 1000, 0);
}

function tokenTotals(result: JsonObject): {
  input: Numeric;
  cache: Numeric;
  output: Numeric;
  cost: Numeric;
} {
  const contexts = collectAgentContexts(result);
  return {
    input: sumOptional(contexts, "n_input_tokens"),
    cache: sumOptional(contexts, "n_cache_tokens"),
    output: sumOptional(contexts, "n_output_tokens"),
    cost: sumOptional(contexts, "cost_usd"),
  };
}

function collectAgentContexts(result: JsonObject): JsonObject[] {
  const contexts: JsonObject[] = [];
  const agentResult = asObject(result.agent_result);
  if (Object.keys(agentResult).length > 0) contexts.push(agentResult);

  for (const step of Array.isArray(result.step_results) ? result.step_results : []) {
    const stepAgentResult = asObject(asObject(step).agent_result);
    if (Object.keys(stepAgentResult).length > 0) contexts.push(stepAgentResult);
  }
  return contexts;
}

function sumOptional(objects: JsonObject[], key: string): Numeric {
  let total = 0;
  let found = false;
  for (const object of objects) {
    const value = asNumber(object[key]);
    if (value === undefined) continue;
    total += value;
    found = true;
  }
  return found ? total : "";
}

function extractRewards(result: JsonObject): Record<string, number> {
  const rawRewards = asObject(asObject(result.verifier_result).rewards);
  return Object.fromEntries(
    Object.entries(rawRewards).flatMap(([key, value]) => {
      const numberValue = asNumber(value);
      return numberValue === undefined ? [] : [[key, numberValue]];
    }),
  );
}

function primaryReward(rewards: Record<string, number>): Numeric {
  if (typeof rewards.reward === "number") return rewards.reward;
  if (typeof rewards.score === "number") return rewards.score;
  const values = Object.values(rewards);
  return values.length === 1 ? values[0] : "";
}

function parseTrialResult(filePath: string, context: ExportContext): TrialRow | undefined {
  const result = readJson(filePath);
  if (!result || typeof result.task_name !== "string" || typeof result.trial_name !== "string") {
    return undefined;
  }

  const agentInfo = asObject(result.agent_info);
  const modelInfo = asObject(agentInfo.model_info);
  const exceptionInfo = asObject(result.exception_info);
  const task = parseTaskName(result.task_name);
  const rewards = extractRewards(result);
  const reward = primaryReward(rewards);
  const tokens = tokenTotals(result);

  return {
    run_id: context.runId,
    job_name: context.jobName,
    trial_name: result.trial_name,
    task_name: result.task_name,
    task_family: task.taskFamily,
    profile: task.profile,
    agent: asString(agentInfo.name),
    model: asString(modelInfo.name),
    attempt_index: 0,
    reward,
    passed: typeof reward === "number" && reward >= 1,
    exception_type: asString(exceptionInfo.exception_type),
    exception_message: asString(exceptionInfo.exception_message),
    started_at: asString(result.started_at),
    finished_at: asString(result.finished_at),
    duration_sec: durationSec({
      started_at: result.started_at,
      finished_at: result.finished_at,
    }),
    environment_setup_duration_sec: durationSec(result.environment_setup),
    agent_setup_duration_sec: durationSec(result.agent_setup),
    agent_execution_duration_sec: durationSec(result.agent_execution),
    verifier_duration_sec: durationSec(result.verifier),
    input_tokens: tokens.input,
    cache_tokens: tokens.cache,
    output_tokens: tokens.output,
    cost_usd: tokens.cost,
    task_checksum: asString(result.task_checksum),
    git_sha: context.gitSha,
    docs_lock_sha: context.docsLockSha,
    result_path: filePath,
    rewards,
  };
}

function assignAttemptIndexes(rows: TrialRow[]): TrialRow[] {
  const counts = new Map<string, number>();
  return rows
    .sort((a, b) => a.trial_name.localeCompare(b.trial_name))
    .map((row) => {
      const key = [row.task_name, row.agent, row.model].join("\0");
      const attemptIndex = (counts.get(key) ?? 0) + 1;
      counts.set(key, attemptIndex);
      return { ...row, attempt_index: attemptIndex };
    });
}

function rewardColumns(rows: TrialRow[]): string[] {
  return [...new Set(rows.flatMap((row) => Object.keys(row.rewards)))]
    .sort()
    .map((key) => `verifier_reward_${key}`);
}

function trialCsvRows(rows: TrialRow[]): Record<string, unknown>[] {
  return rows.map(({ rewards, ...row }) => ({
    ...row,
    ...Object.fromEntries(
      Object.entries(rewards).map(([key, value]) => [`verifier_reward_${key}`, value]),
    ),
  }));
}

function writeCsv(filePath: string, columns: string[], rows: Record<string, unknown>[]) {
  fs.writeFileSync(filePath, stringify(rows, { columns, header: true }));
}

function sumNumbers(values: Numeric[]): number {
  let sum = 0;
  for (const value of values) {
    if (typeof value === "number") sum += value;
  }
  return sum;
}

function groupRows(rows: TrialRow[]): Map<string, TrialRow[]> {
  const groups = new Map<string, TrialRow[]>();
  for (const row of rows) {
    const key = [row.model, row.agent, row.task_name, row.task_family, row.profile].join("\0");
    groups.set(key, [...(groups.get(key) ?? []), row]);
  }
  return groups;
}

export function summarizeRows(rows: TrialRow[]): SummaryRow[] {
  return [...groupRows(rows).values()]
    .map((group) => summarizeGroup(group))
    .sort((a, b) =>
      [a.model, a.task_name, a.profile].join("\0").localeCompare(
        [b.model, b.task_name, b.profile].join("\0"),
      ),
    );
}

function summarizeGroup(group: TrialRow[]): SummaryRow {
  const first = group[0];
  const rewards = group
    .map((row) => row.reward)
    .filter((value): value is number => typeof value === "number");
  const nPassed = group.filter((row) => row.passed).length;

  return {
    run_id: first.run_id,
    job_name: first.job_name,
    model: first.model,
    agent: first.agent,
    task_name: first.task_name,
    task_family: first.task_family,
    profile: first.profile,
    n_trials: group.length,
    n_passed: nPassed,
    pass_rate: group.length === 0 ? 0 : nPassed / group.length,
    n_errors: group.filter((row) => row.exception_type).length,
    mean_reward:
      rewards.length === 0
        ? ""
        : rewards.reduce((sum, value) => sum + value, 0) / rewards.length,
    input_tokens: sumNumbers(group.map((row) => row.input_tokens)),
    cache_tokens: sumNumbers(group.map((row) => row.cache_tokens)),
    output_tokens: sumNumbers(group.map((row) => row.output_tokens)),
    cost_usd: sumNumbers(group.map((row) => row.cost_usd)),
  };
}

export function exportResults(options: ExportOptions): {
  runId: string;
  outDir: string;
  trials: TrialRow[];
  summary: SummaryRow[];
} {
  const jobDir = path.resolve(options.jobDir);
  if (!fs.existsSync(jobDir)) {
    throw new Error(`Job directory not found: ${jobDir}`);
  }

  const metadata = readMetadata(jobDir);
  const runId = options.runId ?? defaultRunId(jobDir, metadata);
  const outDir = path.resolve(options.outDir ?? defaultOutDir(jobDir));
  const context = buildContext(jobDir, runId, metadata);
  const trials = assignAttemptIndexes(
    resultFiles(jobDir)
      .map((filePath) => parseTrialResult(filePath, context))
      .filter((row): row is TrialRow => row !== undefined),
  );
  const summary = summarizeRows(trials);

  fs.mkdirSync(outDir, { recursive: true });
  writeCsv(
    path.join(outDir, "trials.csv"),
    [...TRIAL_COLUMNS, ...rewardColumns(trials)],
    trialCsvRows(trials),
  );
  writeCsv(path.join(outDir, "summary.csv"), [...SUMMARY_COLUMNS], summary);
  writeSummaryJson(path.join(outDir, "summary.json"), jobDir, runId, trials, summary);

  return { runId, outDir, trials, summary };
}

function writeSummaryJson(
  filePath: string,
  jobDir: string,
  runId: string,
  trials: TrialRow[],
  summary: SummaryRow[],
) {
  fs.writeFileSync(
    filePath,
    `${JSON.stringify(
      {
        schema_version: 1,
        run_id: runId,
        job_dir: jobDir,
        exported_at: new Date().toISOString(),
        n_trials: trials.length,
        reward_keys: [...new Set(trials.flatMap((row) => Object.keys(row.rewards)))].sort(),
        summary,
      },
      null,
      2,
    )}\n`,
  );
}

function cliOptions(argv: string[]): ExportOptions {
  const program = new Command()
    .name("results:export")
    .description("Export Harbor trial results to CSV and JSON.")
    .requiredOption("--job <path>", "Harbor job directory, for example runs/<run_id>/harbor-job")
    .option("--run-id <name>", "Run id to write into exports")
    .option("--out-dir <path>", "Output directory, defaults to runs/<run_id>/exports")
    .showHelpAfterError();

  program.parse(argv);
  const options = program.opts<{ job: string; runId?: string; outDir?: string }>();
  return {
    jobDir: options.job,
    runId: options.runId,
    outDir: options.outDir,
  };
}

const currentFile = fileURLToPath(import.meta.url);
if (process.argv[1] && path.resolve(process.argv[1]) === currentFile) {
  try {
    const result = exportResults(cliOptions(process.argv));
    console.log(`Exported ${result.trials.length} trials to ${result.outDir}`);
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}
