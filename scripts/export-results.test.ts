import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { parse } from "csv-parse/sync";

import { exportResults, parseTaskName, summarizeRows } from "./export-results.ts";

function tempDir(): string {
  return fs.mkdtempSync(path.join(os.tmpdir(), "tempo-bench-export-"));
}

function writeJson(filePath: string, value: unknown) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

function trial(overrides: Record<string, unknown>) {
  return {
    task_name: "transfer-with-memo-fee-payer-mcp",
    trial_name: "trial-1",
    task_checksum: "sha256:task",
    agent_info: {
      name: "claude-code",
      model_info: {
        name: "claude-haiku-4-5",
      },
    },
    verifier_result: {
      rewards: {
        reward: 1,
        correctness: 1,
      },
    },
    agent_result: {
      n_input_tokens: 10,
      n_cache_tokens: 2,
      n_output_tokens: 5,
      cost_usd: 0.01,
    },
    started_at: "2026-07-07T10:00:00.000Z",
    finished_at: "2026-07-07T10:01:00.000Z",
    agent_execution: {
      started_at: "2026-07-07T10:00:10.000Z",
      finished_at: "2026-07-07T10:00:40.000Z",
    },
    ...overrides,
  };
}

test("parseTaskName handles multi-hyphen task families", () => {
  assert.deepEqual(parseTaskName("transfer-with-memo-fee-payer-mcp"), {
    taskFamily: "transfer-with-memo-fee-payer",
    profile: "mcp",
  });
  assert.deepEqual(parseTaskName("custom-task"), {
    taskFamily: "custom-task",
    profile: "unknown",
  });
});

test("exportResults writes trial and summary CSV plus JSON", () => {
  const root = tempDir();
  const jobDir = path.join(root, "run-1", "harbor-job");
  writeJson(path.join(root, "run-1", "metadata.json"), {
    run_id: "run-1",
    git_sha: "abc123",
    docs_lock: { sha: "docs123" },
  });
  writeJson(path.join(jobDir, "trial-a", "result.json"), trial({ trial_name: "trial-a" }));
  writeJson(
    path.join(jobDir, "trial-b", "result.json"),
    trial({
      trial_name: "trial-b",
      verifier_result: { rewards: { reward: 0, correctness: 0 } },
      agent_result: {},
    }),
  );
  writeJson(
    path.join(jobDir, "trial-c", "result.json"),
    trial({
      trial_name: "trial-c",
      task_name: "set-fee-token-base",
      agent_info: {
        name: "claude-code",
        model_info: { name: "other-model" },
      },
      verifier_result: undefined,
      exception_info: {
        exception_type: "RuntimeError",
        exception_message: "boom, with comma\nand newline",
      },
    }),
  );

  const result = exportResults({ jobDir });
  assert.equal(result.runId, "run-1");
  assert.equal(result.trials.length, 3);
  assert.equal(result.summary.length, 2);
  assert.equal(result.trials[0].attempt_index, 1);
  assert.equal(result.trials[1].attempt_index, 2);
  assert.equal(result.trials[0].git_sha, "abc123");
  assert.equal(result.trials[0].docs_lock_sha, "docs123");
  assert.equal(result.trials[0].duration_sec, 60);
  assert.equal(result.trials[0].agent_execution_duration_sec, 30);

  const trialsCsv = fs.readFileSync(path.join(result.outDir, "trials.csv"), "utf8");
  assert.match(trialsCsv, /verifier_reward_correctness/);
  assert.match(trialsCsv, /transfer-with-memo-fee-payer/);
  const trialRecords = parse(trialsCsv, { columns: true }) as Record<string, string>[];
  assert.equal(trialRecords.length, 3);
  assert.equal(
    trialRecords.find((record) => record.trial_name === "trial-c")?.exception_message,
    "boom, with comma\nand newline",
  );

  const summaryCsv = fs.readFileSync(path.join(result.outDir, "summary.csv"), "utf8");
  assert.match(summaryCsv, /pass_rate/);
  assert.match(summaryCsv, /other-model/);

  const summaryJson = JSON.parse(
    fs.readFileSync(path.join(result.outDir, "summary.json"), "utf8"),
  ) as { n_trials: number; reward_keys: string[] };
  assert.equal(summaryJson.n_trials, 3);
  assert.deepEqual(summaryJson.reward_keys, ["correctness", "reward"]);
});

test("summarizeRows groups by model, task, and profile", () => {
  const root = tempDir();
  const jobDir = path.join(root, "run-2", "harbor-job");
  writeJson(path.join(jobDir, "a", "result.json"), trial({ trial_name: "a" }));
  writeJson(
    path.join(jobDir, "b", "result.json"),
    trial({
      trial_name: "b",
      agent_info: { name: "claude-code", model_info: { name: "model-b" } },
      verifier_result: { rewards: { reward: 0.5 } },
      agent_result: {
        n_input_tokens: 3,
        n_cache_tokens: 1,
        n_output_tokens: 2,
        cost_usd: 0.02,
      },
    }),
  );
  const exported = exportResults({ jobDir, runId: "run-2" });
  const summary = summarizeRows(exported.trials);

  assert.equal(summary.length, 2);
  assert.equal(summary.find((row) => row.model === "model-b")?.mean_reward, 0.5);
  assert.equal(summary.find((row) => row.model === "model-b")?.input_tokens, 3);
});
