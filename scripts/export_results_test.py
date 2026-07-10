from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.compare_mcp_results import compare, summarize_quality_comparison
from scripts.export_results import (
    export_results,
    parse_task_name,
    summarize_quality,
    summarize_rows,
)


def write_json(file_path: Path, value: Any) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(f"{json.dumps(value, indent=2)}\n")


def trial(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {
        "task_name": "transfer-with-memo-fee-payer-mcp",
        "trial_name": "trial-1",
        "task_checksum": "sha256:task",
        "agent_info": {
            "name": "claude-code",
            "model_info": {
                "name": "claude-haiku-4-5",
            },
        },
        "verifier_result": {
            "rewards": {
                "reward": 1,
                "correctness": 1,
            },
        },
        "agent_result": {
            "n_input_tokens": 10,
            "n_cache_tokens": 2,
            "n_output_tokens": 5,
            "cost_usd": 0.01,
        },
        "started_at": "2026-07-07T10:00:00.000Z",
        "finished_at": "2026-07-07T10:01:00.000Z",
        "agent_execution": {
            "started_at": "2026-07-07T10:00:10.000Z",
            "finished_at": "2026-07-07T10:00:40.000Z",
        },
    }
    value.update(overrides or {})
    return value


class ExportResultsTest(unittest.TestCase):
    def test_parse_task_name_handles_multi_hyphen_task_families(self) -> None:
        self.assertEqual(
            parse_task_name("transfer-with-memo-fee-payer-mcp"),
            {"task_family": "transfer-with-memo-fee-payer", "profile": "mcp"},
        )
        self.assertEqual(
            parse_task_name("tempo-v1/transfer-with-memo", "mcp"),
            {"task_family": "tempo-v1/transfer-with-memo", "profile": "mcp"},
        )
        self.assertEqual(
            parse_task_name("custom-task"),
            {"task_family": "custom-task", "profile": "unknown"},
        )

    def test_export_results_writes_trial_and_summary_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tempo-bench-export-") as root:
            root_path = Path(root)
            job_dir = root_path / "run-1" / "harbor-job"
            write_json(
                root_path / "run-1" / "metadata.json",
                {
                    "run_id": "run-1",
                    "git_sha": "abc123",
                    "docs_source": "docs123",
                },
            )
            write_json(
                job_dir / "trial-a" / "result.json", trial({"trial_name": "trial-a"})
            )
            write_json(
                job_dir / "trial-b" / "result.json",
                trial(
                    {
                        "trial_name": "trial-b",
                        "verifier_result": {"rewards": {"reward": 0, "correctness": 0}},
                        "agent_result": {},
                    },
                ),
            )
            write_json(
                job_dir / "trial-c" / "result.json",
                trial(
                    {
                        "trial_name": "trial-c",
                        "task_name": "tempo-v1/set-fee-token",
                        "agent_info": {
                            "name": "claude-code",
                            "model_info": {"name": "other-model"},
                        },
                        "verifier_result": None,
                        "exception_info": {
                            "exception_type": "RuntimeError",
                            "exception_message": "boom, with comma\nand newline",
                        },
                    },
                ),
            )

            result = export_results(job_dir)
            self.assertEqual(result["run_id"], "run-1")
            self.assertEqual(len(result["trials"]), 3)
            self.assertEqual(len(result["summary"]), 2)
            self.assertEqual(result["trials"][0]["attempt_index"], 1)
            self.assertEqual(result["trials"][1]["attempt_index"], 2)
            self.assertEqual(result["trials"][0]["git_sha"], "abc123")
            self.assertEqual(result["trials"][0]["docs_source"], "docs123")
            self.assertEqual(result["trials"][0]["duration_sec"], 60)
            self.assertEqual(result["trials"][0]["agent_execution_duration_sec"], 30)

            out_dir = Path(result["out_dir"])
            trials_csv = (out_dir / "trials.csv").read_text()
            self.assertIn("verifier_reward_correctness", trials_csv)
            self.assertIn("transfer-with-memo-fee-payer", trials_csv)
            trial_records = pd.read_csv(out_dir / "trials.csv", keep_default_na=False)
            self.assertEqual(len(trial_records), 3)
            self.assertEqual(
                trial_records.loc[
                    trial_records["trial_name"] == "trial-c",
                    "exception_message",
                ].iloc[0],
                "boom, with comma\nand newline",
            )

            summary_csv = (out_dir / "summary.csv").read_text()
            self.assertIn("pass_rate", summary_csv)
            self.assertIn("other-model", summary_csv)

            summary_json = json.loads((out_dir / "summary.json").read_text())
            self.assertEqual(summary_json["n_trials"], 3)
            self.assertEqual(summary_json["reward_keys"], ["correctness", "reward"])

    def test_export_results_reads_mcp_profile_from_trial_config(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tempo-bench-export-") as root:
            job_dir = Path(root) / "job"
            write_json(
                job_dir / "trial" / "result.json",
                trial(
                    {
                        "task_name": "tempo-v1/transfer-with-memo",
                        "config": {
                            "agent": {"mcp_servers": [{"name": "tempo"}]},
                        },
                    }
                ),
            )

            result = export_results(job_dir)

            self.assertEqual(result["trials"][0]["profile"], "mcp")

    def test_export_results_reads_mcp_eval_profiles(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tempo-bench-export-") as root:
            job_dir = Path(root) / "job"
            write_json(
                job_dir / "direct" / "result.json",
                trial(
                    {
                        "task_name": "tempo-mcp-v1/wallet-client",
                        "config": {
                            "agent": {"mcp_servers": [{"name": "tempo-direct"}]}
                        },
                    }
                ),
            )
            write_json(
                job_dir / "code" / "result.json",
                trial(
                    {
                        "task_name": "tempo-mcp-v1/wallet-client",
                        "trial_name": "code",
                        "config": {"agent": {"mcp_servers": [{"name": "tempo-code"}]}},
                    }
                ),
            )
            self.assertEqual(
                {row["profile"] for row in export_results(job_dir)["trials"]},
                {"mcp-direct", "mcp-code"},
            )

    def test_export_marks_only_clean_mcp_trials_eligible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tempo-bench-export-") as root:
            job_dir = Path(root) / "job"
            trial_dir = job_dir / "trial"
            write_json(
                trial_dir / "result.json",
                trial(
                    {
                        "task_name": "tempo-mcp-v1/wallet-client",
                        "config": {
                            "agent": {"mcp_servers": [{"name": "tempo-direct"}]}
                        },
                        "verifier_result": {"rewards": {"reward": 1, "quality": 0.8}},
                    }
                ),
            )
            trace = trial_dir / "artifacts" / "var/log/tempo-mcp/direct-trace.jsonl"
            trace.parent.mkdir(parents=True)
            trace.write_text(
                json.dumps(
                    {
                        "method": "tools/call",
                        "tool": "search",
                        "allowed": True,
                        "duration_ms": 12,
                    }
                )
                + "\n"
            )
            (trial_dir / "agent").mkdir()
            (trial_dir / "agent" / "claude-code.txt").write_text(
                json.dumps({"type": "result", "num_turns": 7}) + "\n"
            )

            row = export_results(job_dir)["trials"][0]

            self.assertEqual(row["quality"], 0.8)
            self.assertEqual(row["model_turns"], 7)
            self.assertTrue(row["mcp_used"])
            self.assertTrue(row["mcp_trace_clean"])
            self.assertTrue(row["eligible"])

    def test_compare_pairs_direct_and_code_trials(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tempo-bench-compare-") as root:
            root_path = Path(root)
            direct_path = root_path / "direct.csv"
            code_path = root_path / "code.csv"
            row = {
                "task_family": "tempo-mcp-v1/wallet-client",
                "model": "test",
                "agent": "agent",
                "attempt_index": 1,
                "task_checksum": "task",
                "docs_source": "docs",
                "passed": "true",
                "input_tokens": 20,
                "cache_tokens": 0,
                "output_tokens": 10,
                "model_turns": 2,
                "mcp_calls": 3,
                "duration_sec": 4,
                "agent_execution_duration_sec": 3,
                "cost_usd": 0.01,
            }
            pd.DataFrame([{**row, "profile": "mcp-direct"}]).to_csv(
                direct_path, index=False
            )
            pd.DataFrame(
                [{**row, "profile": "mcp-code", "input_tokens": 12, "mcp_calls": 1}]
            ).to_csv(code_path, index=False)
            result = compare(str(direct_path), str(code_path))
            self.assertEqual(result.loc[0, "input_tokens_delta"], 8)
            self.assertEqual(result.loc[0, "mcp_calls_delta"], 2)

    def test_quality_summaries_preserve_missing_judge_scores(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tempo-bench-quality-") as root:
            root_path = Path(root)
            direct_path = root_path / "direct.csv"
            code_path = root_path / "code.csv"
            base = {
                "task_family": "tempo-mcp-v1/wallet-client",
                "model": "test",
                "agent": "agent",
                "task_checksum": "task",
                "docs_source": "docs",
                "passed": "true",
                "eligible": "true",
                "input_tokens": 20,
                "cache_tokens": 0,
                "output_tokens": 10,
                "model_turns": 2,
                "mcp_calls": 3,
                "duration_sec": 4,
                "agent_execution_duration_sec": 3,
                "cost_usd": 0.01,
            }
            direct = [
                {**base, "attempt_index": 1, "quality": 0.2, "profile": "mcp-direct"},
                {**base, "attempt_index": 2, "quality": 0.4, "profile": "mcp-direct"},
                {**base, "attempt_index": 3, "quality": 0.6, "profile": "mcp-direct"},
            ]
            code = [
                {**base, "attempt_index": 1, "quality": 0.3, "profile": "mcp-code"},
                {**base, "attempt_index": 2, "quality": 0.3, "profile": "mcp-code"},
                {**base, "attempt_index": 3, "quality": "", "profile": "mcp-code"},
            ]
            pd.DataFrame(direct).to_csv(direct_path, index=False)
            pd.DataFrame(code).to_csv(code_path, index=False)

            task_summary, overall_summary = summarize_quality_comparison(
                compare(str(direct_path), str(code_path))
            )

            self.assertEqual(task_summary.loc[0, "n_attempts"], 3)
            self.assertEqual(task_summary.loc[0, "direct_quality_at_k"], 0.6)
            self.assertAlmostEqual(task_summary.loc[0, "code_quality_coverage"], 2 / 3)
            self.assertAlmostEqual(
                task_summary.loc[0, "paired_quality_coverage"], 2 / 3
            )
            self.assertAlmostEqual(task_summary.loc[0, "mean_quality_delta"], 0.0)
            self.assertEqual(overall_summary.loc[0, "n_tasks"], 1)
            self.assertAlmostEqual(overall_summary.loc[0, "direct_quality_at_k"], 0.6)

    def test_summarize_rows_groups_by_model_task_and_profile(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tempo-bench-export-") as root:
            job_dir = Path(root) / "run-2" / "harbor-job"
            write_json(job_dir / "a" / "result.json", trial({"trial_name": "a"}))
            write_json(
                job_dir / "b" / "result.json",
                trial(
                    {
                        "trial_name": "b",
                        "agent_info": {
                            "name": "claude-code",
                            "model_info": {"name": "model-b"},
                        },
                        "verifier_result": {"rewards": {"reward": 0.5}},
                        "agent_result": {
                            "n_input_tokens": 3,
                            "n_cache_tokens": 1,
                            "n_output_tokens": 2,
                            "cost_usd": 0.02,
                        },
                    },
                ),
            )
            exported = export_results(job_dir, run_id="run-2")
            summary = summarize_rows(exported["trials"])

            self.assertEqual(len(summary), 2)
            self.assertEqual(
                next(row for row in summary if row["model"] == "model-b")[
                    "mean_reward"
                ],
                0.5,
            )
            self.assertEqual(
                next(row for row in summary if row["model"] == "model-b")[
                    "input_tokens"
                ],
                3,
            )

    def test_quality_summary_reports_task_weighted_quality_at_k(self) -> None:
        rows = [
            {
                "run_id": "run",
                "job_name": "job",
                "model": "model",
                "agent": "agent",
                "profile": "mcp-code",
                "task_family": "task-a",
                "trial_name": "a-1",
                "quality": 0.2,
            },
            {
                "run_id": "run",
                "job_name": "job",
                "model": "model",
                "agent": "agent",
                "profile": "mcp-code",
                "task_family": "task-a",
                "trial_name": "a-2",
                "quality": 0.8,
            },
            {
                "run_id": "run",
                "job_name": "job",
                "model": "model",
                "agent": "agent",
                "profile": "mcp-code",
                "task_family": "task-b",
                "trial_name": "b-1",
                "quality": "",
            },
        ]

        summary = summarize_quality(rows)

        self.assertEqual(summary[0]["n_tasks"], 2)
        self.assertEqual(summary[0]["n_quality_scored"], 2)
        self.assertAlmostEqual(summary[0]["quality_coverage"], 2 / 3)
        self.assertEqual(summary[0]["quality_at_k"], 0.8)


if __name__ == "__main__":
    unittest.main()
