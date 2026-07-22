from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts.run_benchmark import (
    MCP_CODE_PROFILE,
    MCP_DIRECT_PROFILE,
    MCP_PROFILE,
    BenchmarkKey,
    apply_pair_id,
    apply_profile,
    build_images,
    daytona_images,
    finalize_config,
    main,
    parse_args,
    parse_model_config,
    preflight,
    prepare_production_profiles,
    production_job,
    production_revision_env,
    render_job_config,
    run_benchmark_key,
    run_benchmark_variant,
    run_production_variant,
    stage_filtered_config,
    stage_pinned_docs_task,
    sync_dataset,
    uses_live_mcp_eval,
    validate_run_options,
    versioned_name,
)


def base_config() -> dict[str, Any]:
    return {"agents": [{"name": "oracle"}], "datasets": []}


def production_model_config() -> dict[str, Any]:
    return {
        "judge_model": "anthropic/claude-haiku-4-5-20251001",
        "models": [{"agent": "claude-code", "model_name": "claude-haiku-4-5"}],
    }


class RunBenchmarkTest(unittest.TestCase):
    def test_concurrent_profiles_build_the_image_pair_once(self) -> None:
        with (
            patch("scripts.run_benchmark.run") as run,
            patch("scripts.run_benchmark._images_built", False),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            list(executor.map(lambda _: build_images(), range(2)))

        self.assertEqual(run.call_count, 3)
        self.assertEqual(run.call_args.args[0], "bash")
        self.assertEqual(run.call_args.args[1][0], "ci_checks/check-image-boundary.sh")

    def test_finalize_config_defaults_to_tempo_suite(self) -> None:
        config = finalize_config(base_config(), {})

        self.assertEqual(
            config["datasets"],
            [
                {
                    "path": "tasks/tempo-v1",
                }
            ],
        )

    def test_finalize_config_selects_mpp_suite(self) -> None:
        config = finalize_config(base_config(), {"task_suite": "mpp"})

        self.assertEqual(
            config["datasets"],
            [{"path": "tasks/mpp"}],
        )

    def test_finalize_config_selects_tempo_mcp_suite(self) -> None:
        self.assertEqual(
            finalize_config(base_config(), {"task_suite": "tempo-mcp"})["datasets"],
            [{"path": "tasks/tempo-mcp-v1"}],
        )

    def test_claude_preflight_accepts_proxy_credentials(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ANTHROPIC_BASE_URL": "http://localhost:4000",
                "ANTHROPIC_AUTH_TOKEN": "token",
            },
            clear=True,
        ):
            preflight({"needs_agent_auth": True, "default_agent": "claude-code"}, {})

    def test_codex_preflight_accepts_openai_api_key_and_base_url(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_BASE_URL": "http://localhost:4000/v1",
                "OPENAI_API_KEY": "token",
            },
            clear=True,
        ):
            preflight(
                {"needs_agent_auth": True, "default_agent": "claude-code"},
                {"agent": "codex"},
            )

    def test_codex_job_preflight_accepts_openai_api_key_and_base_url(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_BASE_URL": "http://localhost:4000/v1",
                "OPENAI_API_KEY": "token",
            },
            clear=True,
        ):
            preflight(
                {
                    "needs_agent_auth": True,
                    "job": {"agents": [{"name": "codex"}]},
                },
                {},
            )

    def test_codex_preflight_rejects_missing_auth(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(RuntimeError, "Missing Codex auth"),
        ):
            preflight(
                {"needs_agent_auth": True, "default_agent": "claude-code"},
                {"agent": "codex"},
            )

    def test_tempo_mcp_suite_uses_the_live_mcp_server(self) -> None:
        self.assertTrue(uses_live_mcp_eval({"task_suite": "tempo-mcp"}))
        self.assertFalse(uses_live_mcp_eval({"task_suite": "tempo"}))

    def test_live_mcp_eval_skips_pinned_docs_preparation(self) -> None:
        options = {
            "profile": "mcp-direct",
            "task_suite": "tempo-mcp",
            "sync": False,
            "env_file": None,
            "job_name": "live-mcp-test",
        }
        with (
            patch("scripts.run_benchmark.preflight"),
            patch("scripts.run_benchmark.preflight_mcp_target"),
            patch("scripts.run_benchmark.ensure_docs_bundle") as ensure_bundle,
            patch(
                "scripts.run_benchmark.stage_daytona_config", return_value="job.yaml"
            ) as stage,
            patch("scripts.run_benchmark.run") as run,
        ):
            run_benchmark_variant("daytona-agent-dev", options)

        ensure_bundle.assert_not_called()
        self.assertIsNone(stage.call_args.args[2])
        run.assert_called_once()

    def test_production_profile_appends_to_explicit_run_group(self) -> None:
        options = {
            "env_file": None,
            "job_name": "production-mcp",
            "profile": "mcp",
            "sync": False,
            "task_suite": "tempo",
        }
        with (
            patch("scripts.run_benchmark.load_env_file"),
            patch("scripts.run_benchmark.preflight"),
            patch("scripts.run_benchmark.preflight_mcp_target"),
            patch("scripts.run_benchmark.docs_source", return_value={"mode": "public"}),
            patch("scripts.run_benchmark.ensure_docs_bundle", return_value=None),
            patch("scripts.run_benchmark.run_production_variant") as run_production,
            patch("scripts.run_benchmark.run") as run,
        ):
            run_benchmark_variant("production-daytona", options)

        run_production.assert_called_once()
        self.assertEqual(run_production.call_args.args[0], "production-mcp-mcp")
        run.assert_not_called()

    def test_production_single_profile_uses_timestamped_run_name(self) -> None:
        options = {
            "env_file": None,
            "job_name": None,
            "profile": "docs",
            "sync": False,
            "task_suite": "tempo",
        }
        with (
            patch("scripts.run_benchmark.load_env_file"),
            patch("scripts.run_benchmark.preflight"),
            patch("scripts.run_benchmark.preflight_mcp_target"),
            patch("scripts.run_benchmark.docs_source", return_value={"mode": "public"}),
            patch("scripts.run_benchmark.ensure_docs_bundle", return_value=None),
            patch(
                "scripts.run_benchmark.production_timestamp",
                return_value="20260714T202823Z",
            ),
            patch("scripts.run_benchmark.run_production_variant") as run_production,
        ):
            run_benchmark_variant("production-daytona", options)

        self.assertEqual(
            run_production.call_args.args[0],
            "stable-bench-v1-production-20260714T202823Z-docs",
        )

    def test_production_profiles_share_one_timestamped_run_group(self) -> None:
        with (
            patch(
                "scripts.run_benchmark.production_timestamp",
                return_value="20260714T202823Z",
            ),
            patch("scripts.run_benchmark.prepare_production_profiles") as prepare,
            patch("scripts.run_benchmark.run_benchmark_variant") as run_variant,
        ):
            main(
                [
                    "production-daytona",
                    "--profile",
                    "all",
                    "--models-config",
                    "config/models.dev.yaml",
                ]
            )

        prepare.assert_called_once()
        profiles = {
            invocation.args[1]["profile"]: invocation.args[1]
            for invocation in run_variant.call_args_list
        }
        run_group = "stable-bench-v1-production-20260714T202823Z"
        self.assertEqual(set(profiles), {"docs", "mcp"})
        self.assertTrue(
            all(options["job_name"] == run_group for options in profiles.values())
        )
        self.assertTrue(
            all(options["pair_id"] == run_group for options in profiles.values())
        )
        self.assertTrue(all(not options["sync"] for options in profiles.values()))

    def test_local_profiles_sync_once_before_running_in_parallel(self) -> None:
        with (
            patch("scripts.run_benchmark.sync_dataset") as sync_dataset,
            patch("scripts.run_benchmark.run_benchmark_variant") as run_variant,
        ):
            main(["local-agent-dev", "--profile", "all"])

        sync_dataset.assert_called_once()
        self.assertEqual(run_variant.call_count, 2)
        self.assertTrue(
            all(not call.args[1]["sync"] for call in run_variant.call_args_list)
        )

    def test_mcp_profiles_refresh_the_mcp_dataset_before_running(self) -> None:
        with (
            patch("scripts.run_benchmark.sync_generated") as sync_generated,
            patch("scripts.run_benchmark.run") as run,
            patch("scripts.run_benchmark.run_benchmark_variant"),
        ):
            main(
                [
                    "local-agent",
                    "--task-suite",
                    "tempo-mcp",
                    "--profile",
                    "mcp-both",
                ]
            )

        sync_generated.assert_called_once()
        run.assert_called_once_with(
            "uv", ["run", "harbor", "sync", "tasks/tempo-mcp-v1"]
        )

    def test_all_suite_refreshes_each_dataset(self) -> None:
        with (
            patch("scripts.run_benchmark.sync_generated"),
            patch("scripts.run_benchmark.run") as run,
        ):
            sync_dataset({"task_suite": "all"})

        self.assertEqual(
            [call.args[1][-1] for call in run.call_args_list],
            ["tasks/tempo-v1", "tasks/tempo-mcp-v1", "tasks/mpp"],
        )

    def test_mcp_pair_preflights_live_target_once_before_parallel_jobs(self) -> None:
        with (
            patch("scripts.run_benchmark.load_env_file"),
            patch("scripts.run_benchmark.preflight_mcp_target") as preflight_target,
            patch("scripts.run_benchmark.run_benchmark_variant") as run_variant,
        ):
            main(
                [
                    "daytona-agent-dev",
                    "--profile",
                    "mcp-both",
                    "--task-suite",
                    "tempo-mcp",
                    "--job-name",
                    "paired-run",
                ]
            )

        preflight_target.assert_called_once()
        self.assertTrue(
            all(
                invocation.args[1]["mcp_target_preflight_done"]
                for invocation in run_variant.call_args_list
            )
        )

    def test_dev_and_production_model_configs_are_distinct(self) -> None:
        dev = parse_model_config("config/models.dev.yaml", None)
        production = parse_model_config("config/models.production.yaml", None)

        self.assertEqual(
            [model["model_name"] for model in dev["models"]],
            ["claude-haiku-4-5-20251001"],
        )
        self.assertEqual(dev["judge_model"], "anthropic/claude-haiku-4-5-20251001")
        self.assertEqual(
            production["judge_model"], "anthropic/claude-haiku-4-5-20251001"
        )
        self.assertIsNone(dev["n_concurrent_trials"])
        self.assertEqual(production["n_concurrent_trials"], "16")
        self.assertEqual(
            [model["model_name"] for model in production["models"]],
            [
                "claude-fable-5",
                "claude-opus-4-8",
                "claude-haiku-4-5-20251001",
                "claude-sonnet-5",
                "gpt-5.4-mini-2026-03-17",
                "gpt-5.6-sol",
                "gpt-5.6-terra",
                "gpt-5.6-luna",
            ],
        )
        self.assertEqual([model["n_concurrent"] for model in dev["models"]], ["16"])
        self.assertEqual(
            [model["n_concurrent"] for model in production["models"]],
            ["16"] * 8,
        )
        self.assertEqual(
            production_job("test-run", production, {})["n_concurrent_trials"], 16
        )
        self.assertEqual(
            [
                (model["agent"], model["concurrency_group"])
                for model in production["models"]
            ],
            [("claude-code", "anthropic")] * 4 + [("codex", "openai")] * 4,
        )

    def test_production_profiles_prepare_shared_inputs_once(self) -> None:
        source = {"mode": "pinned", "repo": "tempo/docs", "sha": "docs123"}
        options = {
            "agent_concurrency": None,
            "env_file": None,
            "models_config": "config/models.dev.yaml",
            "sync": True,
            "task_suite": "tempo",
        }
        variant = {"production": True}
        with (
            patch("scripts.run_benchmark.load_env_file") as load_env,
            patch("scripts.run_benchmark.preflight") as preflight,
            patch("scripts.run_benchmark.preflight_production_agents") as agents,
            patch("scripts.run_benchmark.sync_dataset") as sync_dataset,
            patch("scripts.run_benchmark.docs_source", return_value=source),
            patch("scripts.run_benchmark.ensure_docs_bundle") as ensure_bundle,
        ):
            prepare_production_profiles(variant, options)

        load_env.assert_called_once_with(None)
        preflight.assert_called_once_with(variant, options)
        self.assertEqual(
            [model["model_name"] for model in agents.call_args.args[0]["models"]],
            ["claude-haiku-4-5-20251001"],
        )
        sync_dataset.assert_called_once_with(options)
        ensure_bundle.assert_called_once_with(source)

    def test_finalize_config_requires_all_suite_for_full_matrix(self) -> None:
        config = finalize_config(base_config(), {"task_suite": "all"})

        self.assertEqual(
            config["datasets"],
            [
                {
                    "path": "tasks/tempo-v1",
                },
                {
                    "path": "tasks/tempo-mcp-v1",
                },
                {"path": "tasks/mpp"},
            ],
        )

    def test_finalize_config_resolves_versioned_tempo_task_filter(self) -> None:
        config = finalize_config(
            base_config(), {"task_filter": "tempo-v1/transfer-with-memo"}
        )

        self.assertEqual(
            config["datasets"],
            [
                {
                    "path": "tasks/tempo-v1",
                    "task_names": [
                        "tempo-v1/transfer-with-memo",
                        "transfer-with-memo",
                    ],
                }
            ],
        )

    def test_run_names_resolve_from_catalog(self) -> None:
        self.assertEqual(
            versioned_name(BenchmarkKey.TEMPO, "oracle-local"),
            "stable-bench-v1-oracle-local",
        )
        self.assertEqual(
            run_benchmark_key({"benchmark": "tempo"}, "mpp"), BenchmarkKey.MPP
        )
        self.assertEqual(
            run_benchmark_key({"benchmark": "tempo"}, "tempo-mcp"),
            BenchmarkKey.TEMPO_MCP,
        )
        self.assertEqual(
            run_benchmark_key({"benchmark": "tempo"}, "all"), BenchmarkKey.TEMPO
        )

    def test_parse_args_accepts_all_profiles(self) -> None:
        _, options = parse_args(["daytona-agent", "--profile", "all"])

        self.assertEqual(options["profile"], "all")

    def test_parse_args_accepts_production_attempts(self) -> None:
        _, options = parse_args(["production-daytona", "--n-attempts", "1"])

        self.assertEqual(options["n_attempts"], "1")

    def test_model_uses_the_requested_task_suite(self) -> None:
        options = {
            "env_file": None,
            "job_name": "mpp-model-test",
            "profile": "docs",
            "sync": False,
            "task_suite": "mpp",
        }
        with (
            patch("scripts.run_benchmark.preflight"),
            patch("scripts.run_benchmark.build_images"),
            patch("scripts.run_benchmark.docs_source", return_value={"mode": "public"}),
            patch("scripts.run_benchmark.ensure_docs_bundle", return_value=None),
            patch("scripts.run_benchmark.run") as run,
        ):
            run_benchmark_variant("model", options)

        self.assertEqual(
            run.call_args.args[1][3:5],
            ["--path", "tasks/mpp"],
        )

    def test_suite_profiles_are_validated_before_running(self) -> None:
        for suite, profile in (
            ("tempo", "mcp-direct"),
            ("tempo-mcp", "mcp"),
            ("mpp", "mcp"),
            ("all", "all"),
        ):
            with (
                self.subTest(suite=suite, profile=profile),
                self.assertRaisesRegex(RuntimeError, "is not valid"),
            ):
                validate_run_options(
                    "local-agent", {"task_suite": suite, "profile": profile}
                )

    def test_model_rejects_the_all_suite(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires an oracle variant"):
            validate_run_options("model", {"task_suite": "all", "profile": "docs"})

    def test_all_suite_rejects_agent_runs_before_work(self) -> None:
        with patch("scripts.run_benchmark.preflight") as preflight:
            for variant in ("local-agent", "production-daytona"):
                with (
                    self.subTest(variant=variant),
                    self.assertRaisesRegex(RuntimeError, "requires an oracle variant"),
                ):
                    main([variant, "--task-suite", "all"])

        preflight.assert_not_called()

    def test_production_job_uses_native_name_and_requested_attempts(self) -> None:
        run_id = "mpp-bench-v1-production-20260714T202823Z-docs"
        job = production_job(
            run_id,
            production_model_config(),
            {"n_attempts": "1", "task_suite": "mpp"},
        )
        config = render_job_config(job, benchmark=None)

        self.assertEqual(job["job_name"], run_id)
        self.assertEqual(job["jobs_dir"], "jobs")
        self.assertEqual(config["job_name"], run_id)
        self.assertEqual(
            Path(config["jobs_dir"]) / config["job_name"], Path("jobs") / run_id
        )
        self.assertEqual(job["n_attempts"], 1)
        self.assertEqual(job["n_concurrent_trials"], 16)
        self.assertEqual(
            production_job("test-run", production_model_config(), {})["n_attempts"],
            3,
        )
        self.assertEqual(
            production_job("test-run", production_model_config(), {"concurrency": "8"})[
                "n_concurrent_trials"
            ],
            8,
        )
        with (
            patch(
                "scripts.run_benchmark.parse_model_config",
                return_value=production_model_config(),
            ),
            patch("scripts.run_benchmark.preflight_production_agents"),
            patch(
                "scripts.run_benchmark.production_revision_env",
                return_value={
                    "TEMPO_EVALS_SHA": "a" * 40,
                    "TEMPO_DOCS_SHA": "b" * 40,
                },
            ),
            patch(
                "scripts.run_benchmark.stage_daytona_config", return_value="job.yaml"
            ) as stage,
            patch("scripts.run_benchmark.run_status", return_value=0) as run_status,
        ):
            run_production_variant(
                run_id,
                {
                    "task_suite": "mpp",
                    "no_delete": True,
                    "disable_verification": True,
                    "install_only": True,
                    "debug": True,
                },
                None,
            )

        self.assertEqual(stage.call_args.args[0]["job_name"], run_id)
        self.assertEqual(
            stage.call_args.args[0]["verifier"]["env"],
            {
                "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY:-}",
                "REWARDKIT_JUDGE": "anthropic/claude-haiku-4-5-20251001",
                "TEMPO_EVALS_SHA": "a" * 40,
                "TEMPO_DOCS_SHA": "b" * 40,
            },
        )
        run_status.assert_called_once_with(
            "uv",
            [
                "run",
                "harbor",
                "run",
                "-c",
                "job.yaml",
                "--no-delete",
                "--disable-verification",
                "--install-only",
                "--debug",
                "--max-retries",
                "4",
                "-y",
            ],
        )

    def test_production_revision_env_requires_clean_full_shas(self) -> None:
        with (
            patch(
                "scripts.run_benchmark.git_output",
                side_effect=["", "a" * 40],
            ),
            patch(
                "scripts.run_benchmark.docs_source",
                return_value={"mode": "pinned", "repo": "tempo/docs", "sha": "b" * 40},
            ),
        ):
            self.assertEqual(
                production_revision_env({"task_suite": "tempo"}),
                {"TEMPO_EVALS_SHA": "a" * 40, "TEMPO_DOCS_SHA": "b" * 40},
            )

        with (
            patch("scripts.run_benchmark.git_output", return_value="M dirty.py"),
            self.assertRaisesRegex(RuntimeError, "clean tempo-evals checkout"),
        ):
            production_revision_env({"task_suite": "tempo"})

    def test_production_job_rejects_run_id_paths(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "one path component"):
            production_job("nested/run", production_model_config(), {})

    def test_job_backed_variants_reject_agent_override(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "--agent is only supported"):
            validate_run_options(
                "local-agent-dev",
                {"profile": "docs", "task_suite": "tempo", "agent": "codex"},
            )

    def test_job_config_passes_local_proxy_env_by_agent_provider(self) -> None:
        config = render_job_config(
            {
                "job_name": "auth-test",
                "n_attempts": 1,
                "n_concurrent_trials": 2,
                "environment_type": "docker",
                "force_build": False,
                "agents": [
                    {"name": "claude-code", "model_name": "claude-test"},
                    {"name": "codex", "model_name": "gpt-test"},
                    {"name": "oracle"},
                ],
                "datasets": [],
            }
        )
        agents = {agent["name"]: agent for agent in config["agents"]}

        self.assertEqual(
            agents["claude-code"]["env"],
            {
                "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY:-}",
                "ANTHROPIC_AUTH_TOKEN": "${ANTHROPIC_AUTH_TOKEN:-}",
                "ANTHROPIC_BASE_URL": "${ANTHROPIC_BASE_URL:-}",
                "ANTHROPIC_DEFAULT_OPUS_MODEL": "${ANTHROPIC_DEFAULT_OPUS_MODEL:-}",
                "ANTHROPIC_DEFAULT_SONNET_MODEL": "${ANTHROPIC_DEFAULT_SONNET_MODEL:-}",
            },
        )
        self.assertEqual(
            agents["codex"]["env"],
            {
                "OPENAI_API_KEY": "${OPENAI_API_KEY:-}",
                "OPENAI_BASE_URL": "${OPENAI_BASE_URL:-}",
                "CODEX_AUTH_JSON_PATH": "${CODEX_AUTH_JSON_PATH:-}",
            },
        )
        self.assertNotIn("env", agents["oracle"])
        self.assertEqual(
            config["verifier"]["env"],
            {
                "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY:-}",
                "ANTHROPIC_AUTH_TOKEN": "${ANTHROPIC_AUTH_TOKEN:-}",
                "ANTHROPIC_BASE_URL": "${ANTHROPIC_BASE_URL:-}",
                "REWARDKIT_JUDGE": (
                    "${REWARDKIT_JUDGE:-anthropic/claude-haiku-4-5-20251001}"
                ),
            },
        )

    def test_local_codex_variant_is_authored_as_codex(self) -> None:
        config = render_job_config(
            validate_run_options(
                "local-codex-agent-dev", {"profile": "docs", "task_suite": "tempo"}
            )["job"]
        )

        self.assertEqual(config["agents"][0]["name"], "codex")
        self.assertEqual(
            config["agents"][0]["env"],
            {
                "OPENAI_API_KEY": "${OPENAI_API_KEY:-}",
                "OPENAI_BASE_URL": "${OPENAI_BASE_URL:-}",
                "CODEX_AUTH_JSON_PATH": "${CODEX_AUTH_JSON_PATH:-}",
            },
        )

    def test_mcp_profile_is_injected_at_job_level(self) -> None:
        config = {"agents": [{"name": "claude-code"}, {"name": "oracle"}]}

        self.assertEqual(
            apply_profile(config, "mcp")["agents"],
            [
                {"name": "claude-code", "mcp_servers": MCP_PROFILE["mcp_servers"]},
                {"name": "oracle"},
            ],
        )

    def test_mcp_eval_profiles_inject_distinct_bridge_servers(self) -> None:
        for profile, docs_tool in (
            (MCP_DIRECT_PROFILE, "docs_search"),
            (MCP_CODE_PROFILE, "docs_code"),
        ):
            agents = apply_profile(
                {"agents": [{"name": "claude-code"}, {"name": "oracle"}]},
                profile["id"],
            )["agents"]
            self.assertEqual(agents[0]["mcp_servers"], profile["mcp_servers"])
            self.assertEqual(
                agents[1]["env"],
                {
                    "TEMPO_MCP_ORACLE_URL": profile["mcp_servers"][0]["url"],
                    "TEMPO_MCP_ORACLE_DOCS_TOOL": docs_tool,
                },
            )

    def test_pair_id_is_injected_for_non_oracle_agents(self) -> None:
        self.assertEqual(
            apply_pair_id(
                {"agents": [{"name": "claude-code"}, {"name": "oracle"}]},
                "pair-1",
            ),
            {
                "agents": [
                    {"name": "claude-code", "env": {"STABLE_BENCH_PAIR_ID": "pair-1"}},
                    {"name": "oracle"},
                ]
            },
        )

    def test_daytona_images_use_the_supplied_refs(self) -> None:
        self.assertEqual(
            daytona_images(
                {
                    "agent_image": "ghcr.io/tempoxyz/agent:source-test",
                    "verifier_image": "ghcr.io/tempoxyz/verifier:source-test",
                }
            ),
            {
                "agent": "ghcr.io/tempoxyz/agent:source-test",
                "verifier": "ghcr.io/tempoxyz/verifier:source-test",
            },
        )

    def test_daytona_images_require_both_refs(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError, "requires --agent-image and --verifier-image"
        ):
            daytona_images({})

    def test_all_suite_stages_mcp_tasks_without_a_pinned_docs_bundle(self) -> None:
        config = {"agents": [{"name": "oracle"}], "datasets": []}
        options = {"profile": "docs", "task_suite": "all"}
        with (
            patch("scripts.run_benchmark.stage_task_datasets") as stage_tasks,
            patch("scripts.run_benchmark.redirect_dataset_paths") as redirect,
        ):
            stage_filtered_config(config, "all-suite", options, None)

        stage_tasks.assert_called_once()
        redirect.assert_called_once()

    def test_staged_pinned_docs_proxy_only_docs_hostname(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            task_dir = Path(directory) / "transfer-with-memo"
            environment_dir = task_dir / "environment"
            environment_dir.mkdir(parents=True)
            (task_dir / "task.toml").write_text(
                'artifacts = ["/app/package.json"]\n\n'
                "[environment]\n"
                "[environment.env]\n"
                'TEMPO_TOKEN = "0x20c0000000000000000000000000000000000001"\n'
            )
            (environment_dir / "Dockerfile").write_text("FROM node:22-bookworm\n")
            bundle_dir = Path(directory) / "bundle"
            (bundle_dir / "developers").mkdir(parents=True)
            (bundle_dir / "developers" / "llms.txt").write_text("# Tempo Docs\n")
            (bundle_dir / "manifest.json").write_text(json.dumps({"sha": "docs123"}))

            stage_pinned_docs_task(task_dir, str(bundle_dir))

            config = (task_dir / "task.toml").read_text()
            self.assertNotIn("TEMPO_DOCS_URL", config)
            self.assertIn('source = "/var/log/tempo-docs/access.log"', config)
            self.assertIn('service = "tempo-docs"', config)
            self.assertIn(
                "COPY docs-tls/ca.crt "
                "/usr/local/share/ca-certificates/stable-bench-docs.crt",
                (environment_dir / "Dockerfile").read_text(),
            )
            self.assertEqual(
                (environment_dir / ".dockerignore").read_text(),
                "docs-tls/*\n!docs-tls/ca.crt\n",
            )
            self.assertTrue((environment_dir / "docs-tls" / "ca.crt").exists())
            self.assertTrue((environment_dir / "docs-tls" / "docs.crt").exists())
            self.assertTrue((environment_dir / "docs-tls" / "docs.key").exists())
            self.assertFalse((environment_dir / "docs-tls" / "ca.key").exists())
            certificate_check = subprocess.run(
                [
                    "openssl",
                    "x509",
                    "-checkend",
                    str(2 * 24 * 60 * 60),
                    "-noout",
                    "-in",
                    str(environment_dir / "docs-tls" / "docs.crt"),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(certificate_check.returncode, 0)
            certificate = subprocess.run(
                [
                    "openssl",
                    "x509",
                    "-in",
                    str(environment_dir / "docs-tls" / "docs.crt"),
                    "-noout",
                    "-text",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("DNS:docs.tempo.xyz", certificate.stdout)
            self.assertNotIn("DNS:tempo.xyz", certificate.stdout)
            self.assertIn(
                "- docs.tempo.xyz",
                (environment_dir / "docker-compose.yaml").read_text(),
            )
            self.assertNotIn(
                "- tempo.xyz",
                (environment_dir / "docker-compose.yaml").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
