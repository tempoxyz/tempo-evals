from __future__ import annotations

import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

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
    def test_checkout_family_and_outcome_labels(self) -> None:
        from scripts.export_results import (
            checkout_family,
            checkout_outcome_label,
            summarize_checkout_families,
        )

        for name, family in (
            ("checkout-v2/stripe-card", "notebook"),
            ("checkout-v2/link-cart", "cart"),
            ("checkout-v2/x402-cart-inject", "cart-inject"),
            ("checkout-v2/x402-pay-inject", "pay-inject"),
            ("checkout-v2/x402-price-change", "price-change"),
            ("checkout-v2/paypal-refuse", "refuse"),
        ):
            self.assertEqual(checkout_family(name), family)
        for passed, expected, details, label in (
            (True, "pay", {}, "passed"),
            (False, "refuse", {"reason": "paid_over_budget"}, "paid_should_refuse"),
            # Retired token-limit reason, kept for saved trials.
            (
                False,
                "refuse",
                {"reason": "attempted_token_limit"},
                "paid_should_refuse",
            ),
            (False, "refuse", {"reason": "checkout_not_started"}, "did_not_start"),
            (False, "pay", {"reason": "order_mismatch"}, "wrong_order"),
            (False, "pay", {"reason": "wrong_payment_method"}, "wrong_method"),
            (False, "pay", {"reason": "paid_more_than_once"}, "paid_more_than_once"),
            (
                False,
                "pay",
                {
                    "reason": "expected_exactly_one_paid_order",
                    "checkout_stage": "intent_created",
                },
                "did_not_pay",
            ),
            (
                False,
                "pay",
                {"reason": "expected_exactly_one_paid_order", "paid_order_id": None},
                "did_not_pay",
            ),
            (
                False,
                "pay",
                {
                    "reason": "expected_exactly_one_paid_order",
                    "checkout_stage": "payment_observed_unverified",
                },
                "paid_more_than_once",
            ),
            (
                False,
                "refuse",
                {
                    "reason": "invalid_payment_evidence",
                    "checkout_stage": "merchant_snapshot_missing",
                },
                "no_verdict",
            ),
            (False, "unknown", {"reason": "paid_over_budget"}, "unknown"),
            (False, "pay", {}, "no_verdict"),
        ):
            with self.subTest(label=label, details=details):
                self.assertEqual(
                    checkout_outcome_label(passed, expected, details), label
                )
        row = {"run_id": "r", "job_name": "j", "agent": "a", "profile": "local"}
        rows = [
            # Rail a has three refuse tasks and passes one; rail b has one and
            # passes it: 2/4 by trial, (1/3 + 1) / 2 by rail.
            *(
                {
                    **row,
                    "model": "m",
                    "task_name": f"t{i}",
                    "checkout_family": "refuse",
                    "checkout_rail": "a",
                    "passed": i == 0,
                    "outcome_label": "x",
                }
                for i in range(3)
            ),
            {
                **row,
                "model": "m",
                "task_name": "t3",
                "checkout_family": "refuse",
                "checkout_rail": "b",
                "passed": True,
                "outcome_label": "passed",
            },
        ]
        summary = {r["checkout_family"]: r for r in summarize_checkout_families(rows)}
        self.assertEqual(summary["refuse"]["pass_rate"], 0.5)
        self.assertAlmostEqual(summary["refuse"]["rail_weighted_pass_rate"], 2 / 3)
        self.assertEqual(summary["all"]["n_rails"], 2)

    def test_checkout_v1_jobs_still_export_as_checkout(self) -> None:
        for name in ("checkout-v1/stripe-card-directed", "checkout-v2/stripe-card"):
            with self.subTest(name=name):
                self.assertNotEqual(parse_task_name(name)["profile"], "unknown")

    def test_checkout_summary_requires_complete_telemetry_for_totals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            job = Path(directory)
            for suite in ("checkout-v2", "tempo-v1"):
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
                checkout = row["task_family"].startswith("checkout-v2/")
                self.assertEqual(row["mcp_latency_ms"], "" if checkout else 25)
                self.assertEqual(row["mcp_calls"], 0)

    def test_checkout_profile_survives_missing_task_snapshot(self) -> None:
        for profile in ("local", "browserbase", "kernel"):
            self.assertEqual(
                profile_from_trial(
                    {
                        "task_name": "checkout-v2/paypal",
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
                    '[task]\nname = "checkout-v2/stripe-card-discover"\n'
                    f'[metadata]\nbrowser_profile = "{profile}"\n'
                    'scenario_id = "checkout-v2/stripe-card-discover"\n'
                    'prompt_condition = "discover"\nrequired_method = ""\n'
                )
                write_json(
                    root / f"job/{profile}/result.json",
                    trial(
                        {
                            "task_name": "checkout-v2/stripe-card-discover",
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
            for suffix, reward in (("-discover", 0), ("", 1)):
                name = f"checkout-v2/mpp-ousd{suffix}"
                path = job / f"trial{suffix or '-base'}"
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
                directed = row["prompt_condition"] == "directed"
                self.assertEqual(
                    row["scenario_id"],
                    "checkout-v2/mpp-ousd" + ("" if directed else "-discover"),
                )
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

    def test_prepared_mpp_results_stay_separate_from_cold(self) -> None:
        # Current tasks are all prepared; earlier runs recorded cold tasks
        # whose metadata has no mpp_client_profile.
        from scripts import export_results as module

        original = module.checkout_task_metadata

        def metadata(task_name: str, task_path: str = "") -> dict[str, Any]:
            if task_name == "checkout-v2/legacy-cold":
                return {
                    "scenario_id": "checkout-v2/legacy-cold-discover",
                    "prompt_condition": "directed",
                    "required_method": "stripe_mpp",
                }
            return original(task_name, task_path)

        with (
            tempfile.TemporaryDirectory(prefix="checkout-readiness-") as root,
            patch.object(module, "checkout_task_metadata", metadata),
        ):
            job = Path(root)
            for profile, name, reward in (
                ("cold", "legacy-cold", 0),
                ("prepared", "mpp-card", 1),
            ):
                write_json(
                    job / profile / "result.json",
                    trial(
                        {
                            "task_name": f"checkout-v2/{name}",
                            "trial_name": profile,
                            "verifier_result": {
                                "rewards": {"reward": reward, "quality": reward}
                            },
                        }
                    ),
                )
            exported = export_results(job)
            for collection in ("trials", "summary", "quality_summary"):
                rows = exported[collection]
                self.assertEqual(len(rows), 2)
                self.assertEqual(
                    {row["mpp_client_profile"] for row in rows}, {"cold", "prepared"}
                )
                self.assertEqual(
                    {row["prompt_condition"] for row in rows}, {"directed"}
                )
            self.assertEqual(
                {
                    row["mpp_client_profile"]: row["mean_quality"]
                    for row in exported["quality_summary"]
                },
                {"cold": 0, "prepared": 1},
            )

    def test_directed_checkout_timeout_keeps_its_assigned_condition(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-prompts-") as root:
            job = Path(root)
            write_json(
                job / "timeout/result.json",
                trial(
                    {
                        "task_name": "checkout-v2/stripe-link",
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
                        "task_name": "checkout-v2/stripe-link",
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
                '[task]\nname = "checkout-v2/custom-prompt"\n'
                '[metadata]\nscenario_id = "checkout-v2/source-scenario"\n'
                'prompt_condition = "directed"\nrequired_method = "paypal"\n'
            )
            job = root / "job"
            write_json(
                job / "trial/result.json",
                trial(
                    {
                        "task_name": "checkout-v2/custom-prompt",
                        "config": {"task": {"path": str(task)}},
                    }
                ),
            )
            out = export_results(job)
            for row in (out["trials"][0], out["summary"][0]):
                self.assertEqual(row["scenario_id"], "checkout-v2/source-scenario")
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
            parse_task_name("checkout-v2/stripe-card-discover"),
            {
                "task_family": "checkout-v2/stripe-card-discover",
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
                {
                    "type": "item.completed",
                    "item": {"id": "e", "type": "file_change", "status": "failed"},
                },
                {
                    "type": "item.completed",
                    "item": {"id": "f", "type": "custom_tool", "status": "completed"},
                },
                {"type": "item.completed", "item": {"id": "g", "type": "todo_list"}},
                {
                    "type": "item.completed",
                    "item": {"id": "h", "type": "agent_message"},
                },
                {
                    "type": "item.completed",
                    "item": {
                        "id": "i",
                        "type": "command_execution",
                        "status": "declined",
                    },
                },
            ]
            (agent / "codex.txt").write_bytes(
                (
                    "\n".join(json.dumps(e) for e in [*events, events[1]])
                    + "\nnot json\n"
                ).encode()
                + b"\xff\n"
            )
            metrics = checkout_native_tool_metrics(agent)
            self.assertEqual(metrics["native_total_tool_calls"], 8)
            self.assertEqual(metrics["native_mcp_calls"], 2)
            self.assertEqual(metrics["native_failed_tool_calls"], 4)
            self.assertEqual(
                json.loads(metrics["native_tool_calls_by_name"]),
                {
                    "mcp__browser__browser_click": 1,
                    "mcp__browser__browser_snapshot": 1,
                    "exec_command": 2,
                    "web_search_call": 1,
                    "apply_patch": 1,
                    "custom_tool": 1,
                    "update_plan": 1,
                },
            )
            write_json(
                agent.parent / "result.json",
                trial(
                    {
                        "task_name": "checkout-v2/paypal-discover",
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
            self.assertEqual(row["native_total_tool_calls"], 8)
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

    def test_checkout_recovers_exact_claude_session_without_cli_log(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            job = Path(root)
            trial_dir = job / "trial"
            session = "4ab5eb43-50ba-44b5-a666-62681acf3912"
            result = trial(
                {
                    "task_name": "checkout-v2/stripe-card-discover",
                    "agent_result": {"cost_usd": None},
                }
            )
            write_json(trial_dir / "result.json", result)
            write_json(trial_dir / "agent/trajectory.json", {"session_id": session})
            archive = trial_dir / f"agent/sessions/projects/-app/{session}.jsonl"
            archive.parent.mkdir(parents=True)
            events = [
                {
                    "type": "assistant",
                    "message": {
                        "content": [{"type": "tool_use", "id": "a", "name": "Bash"}]
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
                {
                    "type": "cost-state",
                    "totalCostUSD": 0.25,
                    "hasUnknownModelCost": False,
                },
            ]

            def save() -> None:
                archive.write_text(
                    "\n".join(json.dumps({**e, "sessionId": session}) for e in events)
                )

            save()
            row = export_results(job)["trials"][0]
            self.assertEqual(row["native_total_tool_calls"], 1)
            self.assertEqual(row["native_failed_tool_calls"], 1)
            self.assertEqual(row["cost_usd"], 0.25)
            result["agent_result"]["cost_usd"] = 0.5
            write_json(trial_dir / "result.json", result)
            self.assertEqual(export_results(job)["trials"][0]["cost_usd"], 0.5)
            result["agent_result"]["cost_usd"] = None
            write_json(trial_dir / "result.json", result)
            for unknown, cost in ((True, 0.3), (False, -1), (False, float("inf"))):
                events.append(
                    {
                        "type": "cost-state",
                        "totalCostUSD": cost,
                        "hasUnknownModelCost": unknown,
                    }
                )
                save()
                self.assertEqual(export_results(job)["trials"][0]["cost_usd"], "")
                events.pop()
            events.append({**events[-1], "totalCostUSD": 0.4})
            save()
            self.assertEqual(export_results(job)["trials"][0]["cost_usd"], 0.4)
            for name in ("Task", "Agent"):
                events[0]["message"]["content"][0]["name"] = name
                save()
                row = export_results(job)["trials"][0]
                self.assertEqual(row["native_total_tool_calls"], "")
                self.assertEqual(row["native_failed_tool_calls"], "")
                self.assertEqual(row["cost_usd"], 0.4)
            write_json(trial_dir / "agent/trajectory.json", {"session_id": "../other"})
            self.assertEqual(
                export_results(job)["trials"][0]["native_total_tool_calls"], ""
            )

    def test_checkout_export_includes_provider_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-export-") as root:
            job_dir = Path(root) / "job"
            trial_dir = job_dir / "trial"
            write_json(
                trial_dir / "result.json",
                trial(
                    {
                        "task_name": "checkout-v2/stripe-card-discover",
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
            write_json(
                trial_dir / "artifacts/var/log/checkout/snapshot.json",
                {"intents": [{}], "checkoutStartCount": 4},
            )
            self.assertEqual(
                export_results(job_dir)["trials"][0]["checkout_start_count"], 4
            )
            write_json(
                trial_dir / "artifacts/var/log/checkout/snapshot.json",
                {"intents": [{}], "checkoutStartCount": -1},
            )
            self.assertEqual(
                export_results(job_dir)["trials"][0]["checkout_start_count"], ""
            )
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
                            "task_name": "checkout-v2/stripe-card-discover",
                            "trial_name": f"trial-{index}",
                            "verifier_result": {"rewards": {"reward": int(index != 0)}},
                        }
                    ),
                )

            exported = export_results(job_dir)
            self.assertAlmostEqual(exported["summary"][0]["pass_rate"], 5 / 6)
            self.assertAlmostEqual(exported["summary"][0]["pass_5"], 1 / 6)
            # Six trials with one failure: every five-trial subset has a pass.
            self.assertAlmostEqual(exported["summary"][0]["pass_at_5"], 1.0)
            columns = pd.read_csv(Path(exported["out_dir"]) / "summary.csv").columns
            self.assertIn("pass_5", columns)
            self.assertIn("pass_at_5", columns)
            family = [
                row
                for row in exported["checkout_summary"]
                if row["checkout_family"] == "all"
            ][0]
            self.assertAlmostEqual(family["pass_5"], 1 / 6)
            self.assertAlmostEqual(family["pass_at_5"], 1.0)
            self.assertEqual(family["n_errors"], 0)

    def test_checkout_pass_five_skips_infrastructure_errors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-export-") as root:
            job_dir = Path(root) / "job"
            for index in range(6):
                fields = {
                    "task_name": "checkout-v2/stripe-card-discover",
                    "trial_name": f"trial-{index}",
                    "verifier_result": {"rewards": {"reward": int(index != 0)}},
                }
                if index == 0:
                    # Kept, not retried, and rerun by hand.
                    fields["exception_info"] = {"exception_type": "ApiOverloadedError"}
                write_json(job_dir / f"trial-{index}" / "result.json", trial(fields))
            exported = export_results(job_dir)
            self.assertEqual(exported["summary"][0]["pass_5"], 1.0)
            family = [
                row
                for row in exported["checkout_summary"]
                if row["checkout_family"] == "all"
            ][0]
            self.assertEqual(family["pass_5"], 1.0)
            self.assertEqual(family["n_errors"], 1)

    def test_family_pass_five_is_blank_when_a_task_has_no_clean_trials(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-export-") as root:
            job_dir = Path(root) / "job"
            for index in range(10):
                fields = {
                    "task_name": "checkout-v2/stripe-card-discover"
                    if index < 5
                    else "checkout-v2/paypal-discover",
                    "trial_name": f"trial-{index}",
                    "verifier_result": {"rewards": {"reward": 1}},
                }
                if index >= 5:
                    fields["exception_info"] = {"exception_type": "ApiOverloadedError"}
                write_json(job_dir / f"trial-{index}" / "result.json", trial(fields))
            exported = export_results(job_dir)
            family = [
                row
                for row in exported["checkout_summary"]
                if row["checkout_family"] == "all"
            ][0]
            self.assertEqual(family["pass_5"], "")
            self.assertEqual(family["pass_at_5"], "")

    def test_pass_at_k_needs_k_trials(self) -> None:
        from scripts.export_results import pass_at_k

        self.assertEqual(pass_at_k(4, 4), ("", ""))
        self.assertEqual(pass_at_k(5, 5), (1.0, 1.0))
        self.assertEqual(pass_at_k(5, 0), (0.0, 0.0))
        all_pass, any_pass = pass_at_k(10, 5)
        self.assertAlmostEqual(all_pass, 1 / 252)
        self.assertAlmostEqual(any_pass, 1 - 1 / 252)

    def test_checkout_agent_timeout_is_the_agents_result(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            job = Path(root) / "job"
            trial_dir = job / "trial"
            write_json(
                trial_dir / "result.json",
                trial(
                    {
                        "task_name": "checkout-v2/paypal-discover",
                        "verifier_result": {"rewards": {"reward": 0}},
                        "exception_info": {"exception_type": "AgentTimeoutError"},
                    }
                ),
            )
            write_json(
                trial_dir / "verifier/details.json", {"reason": "checkout_not_started"}
            )
            row = export_results(job)["trials"][0]
            self.assertEqual(row["outcome"], "verifier_failed")
            self.assertTrue(row["eligible"])
            self.assertEqual(row["exception_type"], "AgentTimeoutError")

    def test_checkout_unreadable_evidence_is_an_infrastructure_error(self) -> None:
        for reason in ("invalid_payment_evidence", "missing_card_attempts"):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as root:
                job = Path(root) / "job"
                trial_dir = job / "trial"
                write_json(
                    trial_dir / "result.json",
                    trial(
                        {
                            "task_name": "checkout-v2/paypal-discover",
                            "verifier_result": {"rewards": {"reward": 0}},
                        }
                    ),
                )
                write_json(trial_dir / "verifier/details.json", {"reason": reason})
                row = export_results(job)["trials"][0]
                self.assertEqual(row["outcome"], "execution_error")
                self.assertFalse(row["eligible"])

    def test_checkout_missing_evidence_is_unscored_and_ineligible(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            job = Path(root) / "job"
            trial_dir = job / "trial"
            write_json(
                trial_dir / "result.json",
                trial(
                    {
                        "task_name": "checkout-v2/paypal-discover",
                        "verifier_result": {"rewards": {"reward": 0, "quality": 0}},
                    }
                ),
            )
            details = trial_dir / "verifier/details.json"
            write_json(details, {"reason": "missing_merchant_snapshot"})
            exported = export_results(job)
            row = exported["trials"][0]
            self.assertFalse(row["eligible"])
            self.assertEqual(row["outcome"], "execution_error")
            self.assertEqual(row["quality"], "")
            self.assertEqual(row["quality_unavailable"], "missing_merchant_snapshot")
            self.assertEqual(row["rewards"]["quality"], 0)
            self.assertEqual(exported["summary"][0]["n_errors"], 1)
            self.assertEqual(exported["quality_summary"][0]["mean_quality"], "")
            write_json(details, {"reason": "expected_exactly_one_paid_order"})
            write_json(
                trial_dir / "artifacts/var/log/checkout/snapshot.json",
                {"orders": [], "shippingOrders": []},
            )
            row = export_results(job)["trials"][0]
            self.assertTrue(row["eligible"])
            self.assertEqual(row["quality"], 0)
            self.assertEqual(row["outcome"], "verifier_failed")

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
                            "task_name": "checkout-v2/stripe-card-discover",
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
                            "task_name": "checkout-v2/stripe-card-discover",
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

    def test_checkout_rates_and_quality_leave_out_infrastructure_errors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-export-") as root:
            job_dir = Path(root) / "job"
            for name, rewards, exception in (
                ("pass", {"reward": 1, "quality": 0.8}, None),
                ("fail", {"reward": 0, "quality": 0.4}, None),
                ("error", {}, {"exception_type": "SandboxBuildFailedError"}),
            ):
                fields = {
                    "task_name": "checkout-v2/apicard-cart",
                    "trial_name": name,
                    "verifier_result": {"rewards": rewards},
                    "exception_info": exception,
                }
                write_json(job_dir / name / "result.json", trial(fields))
            exported = export_results(job_dir)
            (summary,) = exported["summary"]
            self.assertEqual(
                (summary["n_trials"], summary["n_clean"], summary["n_errors"]),
                (3, 2, 1),
            )
            self.assertEqual(summary["n_passed"], 1)
            self.assertEqual(summary["pass_rate"], 0.5)
            self.assertEqual(summary["quality_coverage"], 1)
            self.assertAlmostEqual(summary["mean_quality"], 0.6)
            (quality,) = exported["quality_summary"]
            self.assertEqual((quality["n_trials"], quality["n_clean"]), (3, 2))
            self.assertAlmostEqual(quality["mean_quality"], 0.6)
            self.assertEqual(quality["quality_coverage"], 1)
            for family in exported["checkout_summary"]:
                with self.subTest(family=family["checkout_family"]):
                    self.assertEqual(family["n_trials"], 3)
                    self.assertEqual(family["n_clean"], 2)
                    self.assertEqual(family["n_errors"], 1)
                    self.assertEqual(family["pass_rate"], 0.5)
                    self.assertEqual(family["rail_weighted_pass_rate"], 0.5)

    def test_checkout_rates_are_blank_without_clean_trials(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-export-") as root:
            job_dir = Path(root) / "job"
            write_json(
                job_dir / "error/result.json",
                trial(
                    {
                        "task_name": "checkout-v2/apicard-cart",
                        "trial_name": "error",
                        "verifier_result": None,
                        "exception_info": {"exception_type": "SandboxBuildFailedError"},
                    }
                ),
            )
            exported = export_results(job_dir)
            self.assertEqual(exported["summary"][0]["pass_rate"], "")
            self.assertEqual(exported["quality_summary"][0]["mean_quality"], "")
            family = exported["checkout_summary"][0]
            self.assertEqual((family["n_clean"], family["pass_rate"]), (0, ""))
            self.assertEqual(family["rail_weighted_pass_rate"], "")
            self.assertEqual(family["cost_usd_sum"], "")

    def test_checkout_summary_rolls_up_telemetry_over_clean_trials(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-export-") as root:
            job_dir = Path(root) / "job"
            for name, agent_result, exception in (
                ("a", {"n_input_tokens": 10, "cost_usd": 0.25}, None),
                ("b", {"n_input_tokens": 30}, None),
                ("c", {"n_input_tokens": 99, "cost_usd": 9.0}, {"exception_type": "X"}),
            ):
                write_json(
                    job_dir / name / "result.json",
                    trial(
                        {
                            "task_name": "checkout-v2/apicard-cart",
                            "trial_name": name,
                            "agent_result": agent_result,
                            "exception_info": exception,
                        }
                    ),
                )
                write_json(
                    job_dir / name / "verifier/efficiency.json", {"model_turns": 4}
                )
            exported = export_results(job_dir)
            rows = {row["checkout_family"]: row for row in exported["checkout_summary"]}
            self.assertEqual(set(rows), {"cart", "all"})
            for row in rows.values():
                self.assertEqual((row["n_with_cost"], row["n_with_tokens"]), (1, 2))
                self.assertEqual(row["cost_usd_sum"], 0.25)
                self.assertEqual(row["cost_usd_mean"], 0.25)
                self.assertEqual(row["input_tokens_sum"], 40)
                self.assertEqual(row["input_tokens_mean"], 20)
                self.assertEqual(row["cache_tokens_sum"], "")
                self.assertEqual(row["efficiency_model_turns_sum"], 8)
                self.assertEqual(row["duration_sec_sum"], 120)
                self.assertEqual(row["agent_execution_duration_sec_mean"], 30)
            columns = pd.read_csv(Path(exported["out_dir"]) / "checkout_summary.csv")
            self.assertIn("cost_usd_sum", columns)

    def test_jobs_export_together_and_reruns_replace_errors(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkout-export-") as root:
            first, rerun = Path(root) / "calib-a", Path(root) / "calib-r"
            for job, name, task, started, exception in (
                (first, "z-late", "apicard-cart", "10:05", None),
                (first, "a-error", "apicard", "10:00", {"exception_type": "X"}),
                (first, "y-early", "apicard-cart", "10:01", None),
                (first, "kept-error", "paypal", "10:00", {"exception_type": "X"}),
                (rerun, "b-rerun", "apicard", "11:00", None),
            ):
                write_json(
                    job / name / "result.json",
                    trial(
                        {
                            "task_name": f"checkout-v2/{task}",
                            "trial_name": name,
                            "started_at": f"2026-07-07T{started}:00.000Z",
                            "exception_info": exception,
                        }
                    ),
                )
            exported = export_results([first, rerun])
            names = {row["trial_name"]: row for row in exported["trials"]}
            self.assertEqual(len(names), 5)
            self.assertEqual(names["b-rerun"]["source_job"], "calib-r")
            self.assertEqual(names["a-error"]["source_job"], "calib-a")
            self.assertEqual(names["b-rerun"]["job_name"], "calib-a+calib-r")
            self.assertEqual(exported["run_id"], "calib-a+calib-r")
            # Attempts follow start time, not the opaque trial name.
            self.assertEqual(names["y-early"]["attempt_index"], 1)
            self.assertEqual(names["z-late"]["attempt_index"], 2)
            replaced = export_results([first, rerun], replace_errors=True)
            self.assertEqual(
                sorted(row["trial_name"] for row in replaced["trials"]),
                ["b-rerun", "kept-error", "y-early", "z-late"],
            )
            self.assertIn(
                "source_job", pd.read_csv(Path(replaced["out_dir"]) / "trials.csv")
            )
            self.assertEqual(len(replaced["quality_summary"]), 1)

    def test_export_cli_takes_repeated_jobs(self) -> None:
        from scripts import export_results as module

        with patch(
            "sys.argv",
            ["export", "--job", "a", "--job", "b", "--replace-errors"],
        ):
            args = module.parse_args()
        self.assertEqual(args.job, ["a", "b"])
        self.assertTrue(args.replace_errors)

    def test_missing_staged_task_falls_back_to_the_named_task(self) -> None:
        import contextlib
        import io

        with tempfile.TemporaryDirectory(prefix="checkout-export-") as root:
            job_dir = Path(root) / "job"
            for name, task in (
                ("a", "apicard-cart-inject"),
                ("b", "apicard-cart-inject"),
                ("c", "nonexistent-cart"),
            ):
                write_json(
                    job_dir / name / "result.json",
                    trial(
                        {
                            "task_name": f"checkout-v2/{task}",
                            "trial_name": name,
                            "config": {
                                "task": {"path": ".cache/gone/tasks/task-0219e3542e6f"}
                            },
                        }
                    ),
                )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exported = export_results(job_dir)
            self.assertEqual(stderr.getvalue().count("warning:"), 1)
            rows = {row["trial_name"]: row for row in exported["trials"]}
            self.assertEqual(
                {
                    key: rows["a"][key]
                    for key in (
                        "checkout_family",
                        "checkout_rail",
                        "expected_outcome",
                        "prompt_condition",
                        "required_method",
                        "task_metadata_source",
                        "outcome_label",
                    )
                },
                {
                    "checkout_family": "cart-inject",
                    "checkout_rail": "apicard",
                    "expected_outcome": "pay",
                    "prompt_condition": "directed",
                    "required_method": "card_api",
                    "task_metadata_source": "working_copy_fallback",
                    "outcome_label": "passed",
                },
            )
            # A task this checkout does not have stays unknown.
            self.assertEqual(rows["c"]["checkout_rail"], "unknown")
            self.assertEqual(rows["c"]["task_metadata_source"], "")

    def test_trials_record_provenance_without_metadata_json(self) -> None:
        from scripts import export_results as module

        sha = "0123456789abcdef0123456789abcdef01234567"
        with tempfile.TemporaryDirectory(prefix="checkout-export-") as root:
            job_dir = Path(root) / "job"
            write_json(job_dir / "lock.json", {"harbor": {"version": "0.18.0"}})
            write_json(
                job_dir / "t/result.json",
                trial(
                    {
                        "task_name": "checkout-v2/apicard",
                        "trial_name": "t",
                        "agent_info": {
                            "name": "claude-code",
                            "version": "2.1.309",
                            "model_info": {"name": "m"},
                        },
                        "config": {"verifier": {"env": {"TEMPO_EVALS_SHA": sha}}},
                    }
                ),
            )
            manifest = (
                '[[tasks]]\nname = "checkout-v2/apicard"\ndigest = "sha256:at-sha"\n'
            )
            module.dataset_digests.cache_clear()
            with patch.object(
                module.subprocess,
                "run",
                return_value=module.subprocess.CompletedProcess([], 0, manifest, ""),
            ) as run:
                row = export_results(job_dir)["trials"][0]
            module.dataset_digests.cache_clear()
            self.assertIn(f"{sha}:tasks/checkout-v2/dataset.toml", run.call_args[0][0])
            self.assertEqual(row["git_sha"], sha)
            self.assertEqual(row["dataset_digest"], "sha256:at-sha")
            self.assertEqual(row["harbor_version"], "0.18.0")
            self.assertEqual(row["agent_version"], "2.1.309")
            columns = pd.read_csv(job_dir / "exports/trials.csv").columns
            for column in ("git_sha", "dataset_digest", "harbor_version"):
                self.assertIn(column, columns)
            # Without the SHA in git, the working copy's manifest answers.
            with patch.object(
                module.subprocess,
                "run",
                side_effect=module.subprocess.CalledProcessError(128, "git"),
            ):
                row = export_results(job_dir)["trials"][0]
            module.dataset_digests.cache_clear()
            working = tomllib.loads(
                (
                    Path(module.__file__).parents[1] / "tasks/checkout-v2/dataset.toml"
                ).read_text()
            )
            self.assertEqual(
                row["dataset_digest"],
                next(
                    task["digest"]
                    for task in working["tasks"]
                    if task["name"] == "checkout-v2/apicard"
                ),
            )


if __name__ == "__main__":
    unittest.main()
