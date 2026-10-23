from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.compare_mcp_results import compare, summarize_quality_comparison
from scripts.export_results import (
    checkout_native_tool_metrics,
    checkout_tool_metrics,
    export_results,
    parse_task_name,
    profile_from_trial,
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
    def test_checkout_summary_requires_complete_telemetry_for_totals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            for suite in ("checkout-v1", "tempo-v1"):
                for index in range(2):
                    write_json(
                        job / f"{suite}-{index}/result.json",
                        trial(
                            {
                                "task_name": f"{suite}/stripe-card-discover",
                                "trial_name": f"{suite}-{index}",
                            }
                        ),
                    )
            rows = export_results(job)["trials"]
            for row in rows:
                row["mcp_latency_ms"] = 25 if row["trial_name"].endswith("-0") else ""
                row["mcp_calls"] = 0
            summaries = summarize_rows(rows)
            for row in summaries:
                checkout = row["task_family"].startswith("checkout-v1/")
                self.assertEqual(row["mcp_latency_ms"], "" if checkout else 25)
                self.assertEqual(row["mcp_calls"], 0)

    def test_checkout_profile_survives_missing_task_snapshot(self) -> None:
        for profile in ("local", "browserbase", "kernel"):
            self.assertEqual(
                profile_from_trial(
                    {
                        "task_name": "checkout-v1/paypal-directed",
                        "config": {
                            "task": {"path": ".cache/deleted-checkout-snapshot"},
                            "agent": {"env": {"CHECKOUT_BROWSER_PROFILE": profile}},
                        },
                    }
                ),
                profile,
            )

    def test_checkout_browser_profiles_remain_separate_in_exports(self) -> None:
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo) as directory:
            root = Path(directory)
            for profile in ("local", "browserbase", "kernel"):
                task = root / profile
                task.mkdir()
                (task / "task.toml").write_text(
                    '[task]\nname = "checkout-v1/stripe-card-discover"\n'
                    f'[metadata]\nbrowser_profile = "{profile}"\n'
                    'scenario_id = "checkout-v1/stripe-card-discover"\n'
                    'prompt_condition = "discover"\nrequired_method = ""\n'
                )
                write_json(
                    root / f"job/{profile}/result.json",
                    trial(
                        {
                            "task_name": "checkout-v1/stripe-card-discover",
                            "trial_name": profile,
                            "config": {"task": {"path": str(task)}},
                        }
                    ),
                )
            result = export_results(root / "job")
            self.assertEqual(
                [row["attempt_index"] for row in result["trials"]], [1, 1, 1]
            )
            for collection in ("trials", "summary", "quality_summary"):
                self.assertEqual(
                    {row["profile"] for row in result[collection]},
                    {"local", "browserbase", "kernel"},
                )

    def test_checkout_prompt_conditions_stay_separate_in_all_exports(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-prompts-") as root:
            job = Path(root)
            for suffix, reward in (("-discover", 0), ("-directed", 1)):
                name = f"checkout-v1/mpp-ousd{suffix}"
                path = job / f"trial{suffix}"
                write_json(
                    path / "result.json",
                    trial(
                        {
                            "task_name": name,
                            "trial_name": path.name,
                            "verifier_result": {
                                "rewards": {"reward": reward, "quality": reward}
                            },
                        }
                    ),
                )
                write_json(
                    path / "verifier/details.json",
                    {
                        "payment_method": "tempo_mpp" if reward else None,
                        "observed_method": "tempo_mpp" if reward else None,
                        "observed_methods": ["tempo_mpp"] if reward else [],
                    },
                )
            exported = export_results(job)
            self.assertEqual(len(exported["summary"]), 2)
            self.assertEqual(len(exported["quality_summary"]), 2)
            for row in exported["trials"]:
                self.assertEqual(row["scenario_id"], "checkout-v1/mpp-ousd-discover")
                directed = row["prompt_condition"] == "directed"
                self.assertEqual(
                    row["required_method"], "tempo_mpp" if directed else ""
                )
                self.assertEqual(
                    row["observed_method"], "tempo_mpp" if directed else ""
                )
                self.assertEqual(row["attempt_index"], 1)
            for rows, metric in (
                (exported["summary"], "pass_rate"),
                (exported["quality_summary"], "mean_quality"),
            ):
                self.assertEqual(
                    {row["prompt_condition"]: row[metric] for row in rows},
                    {"discover": 0, "directed": 1},
                )
            for filename in ("trials.csv", "summary.csv", "quality_summary.csv"):
                frame = pd.read_csv(Path(exported["out_dir"]) / filename)
                self.assertEqual(
                    set(frame["prompt_condition"]), {"discover", "directed"}
                )

    def test_directed_checkout_timeout_keeps_its_assigned_condition(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-prompts-") as root:
            job = Path(root)
            write_json(
                job / "timeout/result.json",
                trial(
                    {
                        "task_name": "checkout-v1/stripe-link-directed",
                        "verifier_result": None,
                        "exception_info": {"exception_type": "AgentTimeoutError"},
                    }
                ),
            )
            row = export_results(job)["trials"][0]
            self.assertEqual(row["prompt_condition"], "directed")
            self.assertEqual(row["required_method"], "link")
            self.assertEqual(row["observed_method"], "")
            self.assertFalse(row["passed"])

    def test_wrong_method_is_observed_without_receiving_credit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            write_json(
                job / "wrong/result.json",
                trial(
                    {
                        "task_name": "checkout-v1/stripe-link-directed",
                        "verifier_result": {
                            "rewards": {"reward": 0, "correctness": 0, "quality": 0}
                        },
                    }
                ),
            )
            write_json(
                job / "wrong/verifier/details.json",
                {
                    "reason": "wrong_payment_method",
                    "payment_method": None,
                    "observed_method": "card",
                    "observed_methods": ["card"],
                },
            )
            agent_log = job / "wrong/agent/claude-code.txt"
            agent_log.parent.mkdir()
            agent_log.write_text('{"type": "result", "num_turns": 99}\n')
            exported = export_results(job)
            row = exported["trials"][0]
            self.assertEqual(row["required_method"], "link")
            self.assertEqual(row["observed_method"], "card")
            self.assertEqual(json.loads(row["observed_methods"]), ["card"])
            self.assertEqual(row["payment_method"], "")
            self.assertEqual(row["reward"], 0)
            self.assertEqual(row["quality"], 0)
            self.assertEqual(row["model_turns"], 99)
            self.assertEqual(row["efficiency_model_turns"], "")

    def test_checkout_exports_use_native_metadata_even_with_nonstandard_task_names(
        self,
    ) -> None:
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=repo) as directory:
            root = Path(directory)
            task = root / "task"
            task.mkdir()
            (task / "task.toml").write_text(
                '[task]\nname = "checkout-v1/custom-prompt"\n'
                '[metadata]\nscenario_id = "checkout-v1/source-scenario"\n'
                'prompt_condition = "directed"\nrequired_method = "paypal"\n'
            )
            job = root / "job"
            write_json(
                job / "trial/result.json",
                trial(
                    {
                        "task_name": "checkout-v1/custom-prompt",
                        "config": {"task": {"path": str(task)}},
                    }
                ),
            )
            out = export_results(job)
            for row in (out["trials"][0], out["summary"][0]):
                self.assertEqual(row["scenario_id"], "checkout-v1/source-scenario")
                self.assertEqual(row["required_method"], "paypal")
                self.assertEqual(row["prompt_condition"], "directed")
            self.assertEqual(out["quality_summary"][0]["prompt_condition"], "directed")

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
        self.assertEqual(
            parse_task_name("checkout-v1/stripe-card-discover"),
            {
                "task_family": "checkout-v1/stripe-card-discover",
                "profile": "browser-mcp",
            },
        )

    def test_export_results_writes_trial_and_summary_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stable-bench-export-") as root:
            root_path = Path(root)
            job_dir = root_path / "jobs" / "run-1"
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
            self.assertEqual(result["trials"][0]["git_sha"], "")
            self.assertEqual(result["trials"][0]["docs_source"], "")
            self.assertEqual(result["trials"][0]["duration_sec"], 60)
            self.assertEqual(result["trials"][0]["agent_execution_duration_sec"], 30)

            out_dir = Path(result["out_dir"])
            self.assertEqual(out_dir, (job_dir / "exports").resolve())
            trials_csv = (out_dir / "trials.csv").read_text()
            self.assertIn("verifier_reward_correctness", trials_csv)
            self.assertIn("transfer-with-memo-fee-payer", trials_csv)
            self.assertNotIn("payment_provider_type", trials_csv)
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
            self.assertNotIn("pass_5", summary_csv)

            summary_json = json.loads((out_dir / "summary.json").read_text())
            self.assertEqual(summary_json["n_trials"], 3)
            self.assertEqual(summary_json["reward_keys"], ["correctness", "reward"])

    def test_checkout_raw_tools_preserve_errors_names_and_missing_data(self) -> None:
        metrics = checkout_tool_metrics(
            {
                "agent": {"version": "pinned"},
                "steps": [
                    {
                        "source": "agent",
                        "tool_calls": [
                            {"function_name": "Bash"},
                            {"function_name": "mcp__browser__browser_click"},
                        ],
                        "observation": {
                            "results": [
                                {
                                    "source_call_id": "call-1",
                                    "content": "### Error: missing element",
                                },
                                {
                                    "source_call_id": "call-1",
                                    "content": "[error] tool reported failure",
                                },
                            ]
                        },
                    },
                    {"source": "agent", "tool_calls": None},
                    {
                        "source": "agent",
                        "is_copied_context": True,
                        "tool_calls": [{"function_name": "Read"}],
                    },
                ],
            }
        )
        self.assertEqual(metrics["total_tool_calls"], 2)
        self.assertEqual(
            json.loads(metrics["tool_calls_by_name"]),
            {"Bash": 1, "mcp__browser__browser_click": 1},
        )
        self.assertEqual(metrics["reported_tool_error_count"], 1)
        self.assertEqual(metrics["agent_harness_version"], "pinned")
        self.assertEqual(checkout_tool_metrics({})["total_tool_calls"], "")
        self.assertEqual(checkout_tool_metrics({"steps": []})["total_tool_calls"], 0)
        self.assertEqual(
            checkout_tool_metrics(
                {"steps": [{"source": "agent", "tool_calls": False}]}
            )["total_tool_calls"],
            "",
        )

    def test_codex_native_tools_include_nested_calls_and_deduplicate(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            agent = Path(root) / "trial" / "agent"
            agent.mkdir(parents=True)
            events = [
                {"type": "thread.started", "thread_id": "test"},
                {
                    "type": "item.completed",
                    "item": {
                        "id": "a",
                        "type": "mcp_tool_call",
                        "server": "browser",
                        "tool": "browser_click",
                        "status": "completed",
                    },
                },
                {
                    "type": "item.completed",
                    "item": {
                        "id": "b",
                        "type": "mcp_tool_call",
                        "server": "browser",
                        "tool": "browser_snapshot",
                        "status": "failed",
                        "error": {"message": "unavailable"},
                    },
                },
                {
                    "type": "item.completed",
                    "item": {"id": "c", "type": "command_execution", "exit_code": 1},
                },
                {
                    "type": "item.completed",
                    "item": {"id": "d", "type": "web_search", "status": "completed"},
                },
            ]
            (agent / "codex.txt").write_text(
                "\n".join(json.dumps(e) for e in [*events, events[1]]) + "\nnot json\n"
            )
            metrics = checkout_native_tool_metrics(agent)
            self.assertEqual(metrics["native_total_tool_calls"], 4)
            self.assertEqual(metrics["native_mcp_calls"], 2)
            self.assertEqual(metrics["native_failed_tool_calls"], 2)
            self.assertEqual(
                json.loads(metrics["native_tool_calls_by_name"]),
                {
                    "mcp__browser__browser_click": 1,
                    "mcp__browser__browser_snapshot": 1,
                    "exec_command": 1,
                    "web_search_call": 1,
                },
            )
            write_json(
                agent.parent / "result.json",
                trial(
                    {
                        "task_name": "checkout-v1/paypal-discover",
                        "agent_info": {"name": "codex", "model_info": {"name": "test"}},
                    }
                ),
            )
            write_json(
                agent / "trajectory.json",
                {
                    "steps": [
                        {"source": "agent", "tool_calls": [{"function_name": "exec"}]}
                    ]
                },
            )
            row = export_results(agent.parent.parent)["trials"][0]
            self.assertEqual(row["total_tool_calls"], 1)
            self.assertEqual(row["native_total_tool_calls"], 4)
            self.assertEqual(row["mcp_calls"], 2)
            self.assertTrue(row["mcp_used"])

    def test_claude_native_tools_distinguish_missing_and_recorded_zero(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            agent = Path(root)
            self.assertEqual(
                checkout_native_tool_metrics(agent)["native_total_tool_calls"], ""
            )
            native = agent / "claude-code.txt"
            native.write_text('{"type":"system","subtype":"init"}\n')
            self.assertEqual(
                checkout_native_tool_metrics(agent)["native_total_tool_calls"], 0
            )
            events = [
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "id": "a", "name": "Bash"},
                            {
                                "type": "tool_use",
                                "id": "b",
                                "name": "mcp__browser__browser_click",
                            },
                        ]
                    },
                },
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "a",
                                "is_error": True,
                            }
                        ]
                    },
                },
            ]
            with native.open("a") as output:
                output.write("\n".join(json.dumps(e) for e in events + events) + "\n")
            metrics = checkout_native_tool_metrics(agent)
            self.assertEqual(metrics["native_total_tool_calls"], 2)
            self.assertEqual(metrics["native_mcp_calls"], 1)
            self.assertEqual(metrics["native_failed_tool_calls"], 1)

    def test_checkout_export_includes_provider_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-export-") as root:
            job_dir = Path(root) / "job"
            trial_dir = job_dir / "trial"
            write_json(
                trial_dir / "result.json",
                trial(
                    {
                        "task_name": "checkout-v1/stripe-card-discover",
                        "verifier_result": {"rewards": {"reward": 1}},
                    }
                ),
            )
            write_json(
                trial_dir / "verifier" / "details.json",
                {
                    "reason": "verified",
                    "payment_method": "card",
                    "checkout_stage": "verified",
                    "payment_provider_type": "stripe_sandbox",
                    "extra_checkout_attempts": 0,
                    "shipping_address_match": True,
                    "shipping_mismatched_fields": [],
                },
            )
            write_json(
                trial_dir / "artifacts/var/log/checkout/snapshot.json",
                {"sessions": [{}, {}], "paymentAttemptCount": 3},
            )
            write_json(
                trial_dir / "verifier" / "efficiency.json",
                {"model_turns": 10, "tool_calls": 3, "trajectory_duration_sec": 150},
            )
            agent_log = trial_dir / "agent" / "claude-code.txt"
            agent_log.parent.mkdir()
            agent_log.write_text('{"type": "result", "num_turns": 99}\n')
            write_json(
                trial_dir / "agent" / "trajectory.json",
                {
                    "steps": [
                        {
                            "source": "agent",
                            "tool_calls": [
                                {"function_name": "Read"},
                                {"function_name": "mcp__browser__browser_navigate"},
                                {"function_name": "mcp__browser__browser_click"},
                            ],
                        },
                        {
                            "source": "agent",
                            "is_copied_context": True,
                            "tool_calls": [
                                {"function_name": "mcp__browser__browser_click"}
                            ],
                        },
                        {"source": "agent", "tool_calls": None},
                    ]
                },
            )

            exported = export_results(job_dir)
            row = exported["trials"][0]
            self.assertEqual(row["profile"], "browser-mcp")
            self.assertEqual(row["payment_method"], "card")
            self.assertEqual(row["checkout_stage"], "verified")
            self.assertEqual(row["payment_provider_type"], "stripe_sandbox")
            self.assertEqual(row["verification_reason"], "verified")
            self.assertEqual(row["extra_checkout_attempts"], 0)
            self.assertEqual(row["model_turns"], 99)
            self.assertEqual(row["efficiency_model_turns"], 10)
            self.assertEqual(row["total_tool_calls"], 3)
            self.assertEqual(row["checkout_start_count"], 2)
            self.assertEqual(row["credentialed_payment_request_count"], 3)
            self.assertTrue(row["shipping_address_match"])
            self.assertEqual(row["shipping_mismatched_fields"], "[]")
            self.assertEqual(sum(json.loads(row["tool_calls_by_name"]).values()), 3)
            self.assertEqual(row["trajectory_duration_sec"], 150)
            self.assertEqual(row["mcp_calls"], 2)
            self.assertTrue(row["mcp_used"])
            self.assertEqual(row["mcp_latency_ms"], "")
            self.assertEqual(row["mcp_denied_calls"], "")
            self.assertEqual(exported["summary"][0]["mcp_calls"], 2)
            self.assertEqual(exported["summary"][0]["mcp_latency_ms"], "")
            self.assertEqual(exported["summary"][0]["mcp_denied_calls"], "")
            self.assertTrue(row["eligible"])
            columns = pd.read_csv(Path(exported["out_dir"]) / "trials.csv").columns
            self.assertIn("payment_provider_type", columns)
            self.assertEqual(exported["summary"][0]["pass_5"], "")

    def test_checkout_prompt_columns_do_not_change_other_suite_exports(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            job = Path(root)
            write_json(job / "trial/result.json", trial())
            write_json(
                job / "trial/agent/trajectory.json",
                {
                    "steps": [
                        {
                            "source": "agent",
                            "tool_calls": [{"function_name": "mcp__tempo__request"}],
                        }
                    ]
                },
            )
            exported = export_results(job)
            self.assertEqual(exported["trials"][0]["mcp_calls"], "")
            for filename in ("trials.csv", "summary.csv", "quality_summary.csv"):
                columns = pd.read_csv(Path(exported["out_dir"]) / filename).columns
                for column in ("scenario_id", "prompt_condition", "required_method"):
                    self.assertNotIn(column, columns)

    def test_checkout_pass_five_uses_independent_trial_outcomes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-export-") as root:
            job_dir = Path(root) / "job"
            for index in range(6):
                write_json(
                    job_dir / f"trial-{index}" / "result.json",
                    trial(
                        {
                            "task_name": "checkout-v1/stripe-card-discover",
                            "trial_name": f"trial-{index}",
                            "verifier_result": {"rewards": {"reward": int(index != 0)}},
                        }
                    ),
                )

            exported = export_results(job_dir)
            self.assertAlmostEqual(exported["summary"][0]["pass_rate"], 5 / 6)
            self.assertAlmostEqual(exported["summary"][0]["pass_5"], 1 / 6)
            columns = pd.read_csv(Path(exported["out_dir"]) / "summary.csv").columns
            self.assertIn("pass_5", columns)

    def test_checkout_export_uses_native_quality(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-quality-") as root:
            job_dir = Path(root) / "job"
            for name, reward, quality in (
                ("success", 1, 1),
                ("retry", 1, 0.8),
                ("failure", 0, 0),
            ):
                write_json(
                    job_dir / name / "result.json",
                    trial(
                        {
                            "task_name": "checkout-v1/stripe-card-discover",
                            "trial_name": name,
                            "verifier_result": {
                                "rewards": {
                                    "reward": reward,
                                    "correctness": reward,
                                    "quality": quality,
                                }
                            },
                        }
                    ),
                )
            exported = export_results(job_dir)
            self.assertAlmostEqual(exported["summary"][0]["mean_quality"], 0.6)
            self.assertAlmostEqual(exported["summary"][0]["pass_rate"], 2 / 3)
            self.assertEqual(exported["summary"][0]["quality_coverage"], 1)
            self.assertNotIn(
                "checkout_score", pd.read_csv(Path(exported["out_dir"]) / "trials.csv")
            )

    def test_checkout_missing_quality_does_not_bias_average_toward_failures(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-quality-") as root:
            job_dir = Path(root) / "job"
            for name, rewards in (
                ("pass", {"reward": 1}),
                ("fail", {"reward": 0, "quality": 0}),
            ):
                write_json(
                    job_dir / name / "result.json",
                    trial(
                        {
                            "task_name": "checkout-v1/stripe-card-discover",
                            "trial_name": name,
                            "verifier_result": {"rewards": rewards},
                        }
                    ),
                )
            exported = export_results(job_dir)
            self.assertEqual(exported["summary"][0]["pass_rate"], 0.5)
            for summary in (exported["summary"][0], exported["quality_summary"][0]):
                self.assertEqual(summary["quality_coverage"], 0.5)
                for metric in ("mean_quality", "median_quality", "quality_at_k"):
                    self.assertEqual(summary[metric], "")

    def test_export_results_reads_mcp_profile_from_trial_config(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stable-bench-export-") as root:
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
        with tempfile.TemporaryDirectory(prefix="stable-bench-export-") as root:
            job_dir = Path(root) / "job"
            write_json(
                job_dir / "direct" / "result.json",
                trial(
                    {
                        "task_name": "tempo-mcp-v1/wallet-client",
                        "config": {
                            "agent": {
                                "mcp_servers": [{"name": "tempo-direct"}],
                                "env": {"STABLE_BENCH_PAIR_ID": "pair-1"},
                            }
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
            rows = export_results(job_dir)["trials"]
            self.assertEqual(
                {row["profile"] for row in rows}, {"mcp-direct", "mcp-code"}
            )
            self.assertEqual({row["docs_source"] for row in rows}, {"live"})

    def test_tempo_passes_use_correctness_instead_of_composite_reward(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stable-bench-export-") as root:
            job_dir = Path(root) / "job"
            write_json(
                job_dir / "trial" / "result.json",
                trial(
                    {
                        "task_name": "tempo-v1/transfer-with-memo",
                        "config": {
                            "agent": {"mcp_servers": [{"name": "tempo"}]},
                        },
                        "verifier_result": {
                            "rewards": {
                                "correctness": 1,
                                "quality": 0.85,
                                "reward": 0.925,
                            }
                        },
                    }
                ),
            )
            trace = job_dir / "trial" / "artifacts" / "tempo" / "trace.jsonl"
            trace.parent.mkdir(parents=True)
            trace.write_text(
                json.dumps({"method": "tools/call", "allowed": True}) + "\n"
            )

            result = export_results(job_dir)

            self.assertTrue(result["trials"][0]["passed"])
            self.assertTrue(result["trials"][0]["eligible"])
            self.assertEqual(result["trials"][0]["outcome"], "passed")
            self.assertEqual(result["summary"][0]["n_passed"], 1)
            self.assertEqual(result["summary"][0]["pass_rate"], 1)

    def test_non_tempo_suites_keep_primary_reward_pass_semantics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stable-bench-export-") as root:
            job_dir = Path(root) / "job"
            write_json(
                job_dir / "trial" / "result.json",
                trial(
                    {
                        "task_name": "mpp/server-charge-pathusd",
                        "verifier_result": {
                            "rewards": {
                                "correctness": 0.75,
                                "quality": 0.6,
                                "reward": 1,
                            }
                        },
                    }
                ),
            )

            result = export_results(job_dir)

            self.assertTrue(result["trials"][0]["passed"])

    def test_export_marks_only_clean_mcp_trials_eligible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stable-bench-export-") as root:
            job_dir = Path(root) / "job"
            trial_dir = job_dir / "trial"
            write_json(
                trial_dir / "result.json",
                trial(
                    {
                        "task_name": "tempo-mcp-v1/wallet-client",
                        "config": {
                            "agent": {
                                "mcp_servers": [{"name": "tempo-direct"}],
                                "env": {"STABLE_BENCH_PAIR_ID": "pair-1"},
                            }
                        },
                        "verifier_result": {
                            "rewards": {
                                "reward": 1,
                                "quality": 0.8,
                                "quality_judge_available": 1,
                            }
                        },
                    }
                ),
            )
            write_json(
                trial_dir / "verifier" / "validation.json",
                {
                    "components": {
                        "schema_valid": 1,
                        "docs_source_valid": 1,
                        "mcp_tool_mix_valid": 1,
                        "data_evidence_valid": 1,
                        "task_requirements_valid": 1,
                    },
                    "errors": [],
                    "warnings": ["documentation provenance in evidence"],
                },
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
            self.assertEqual(row["pair_id"], "pair-1")
            self.assertEqual(row["outcome"], "passed")
            self.assertEqual(row["validation_error_count"], 0)
            self.assertEqual(row["validation_warning_count"], 1)
            self.assertEqual(row["data_evidence_valid"], 1)
            self.assertEqual(row["quality_judge_available"], 1)

    def test_compare_pairs_direct_and_code_trials(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stable-bench-compare-") as root:
            root_path = Path(root)
            direct_path = root_path / "direct.csv"
            code_path = root_path / "code.csv"
            row = {
                "task_family": "tempo-mcp-v1/wallet-client",
                "pair_id": "pair-1",
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

    def test_compare_rejects_unpaired_mcp_trials(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stable-bench-compare-") as root:
            root_path = Path(root)
            direct_path = root_path / "direct.csv"
            code_path = root_path / "code.csv"
            row = {
                "task_family": "tempo-mcp-v1/wallet-client",
                "pair_id": "",
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
            pd.DataFrame([{**row, "profile": "mcp-code"}]).to_csv(
                code_path, index=False
            )

            with self.assertRaisesRegex(ValueError, "pair_id"):
                compare(str(direct_path), str(code_path))

    def test_quality_summaries_preserve_missing_judge_scores(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stable-bench-quality-") as root:
            root_path = Path(root)
            direct_path = root_path / "direct.csv"
            code_path = root_path / "code.csv"
            base = {
                "task_family": "tempo-mcp-v1/wallet-client",
                "pair_id": "pair-1",
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
            self.assertAlmostEqual(task_summary.loc[0, "mean_quality_delta"], 0.0)
            self.assertEqual(overall_summary.loc[0, "n_tasks"], 1)
            self.assertAlmostEqual(overall_summary.loc[0, "direct_quality_at_k"], 0.6)

    def test_summarize_rows_groups_by_model_task_and_profile(self) -> None:
        with tempfile.TemporaryDirectory(prefix="stable-bench-export-") as root:
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
