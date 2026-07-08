from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.export_results import export_results, parse_task_name, summarize_rows


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
                    "docs_lock": {"sha": "docs123"},
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
                        "task_name": "set-fee-token-base",
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
            self.assertEqual(result["trials"][0]["docs_lock_sha"], "docs123")
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


if __name__ == "__main__":
    unittest.main()
