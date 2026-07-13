from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts.run_benchmark import (
    MCP_CODE_PROFILE,
    MCP_DIRECT_PROFILE,
    BenchmarkKey,
    apply_pair_id,
    apply_profile,
    benchmark_provenance,
    daytona_base_image,
    docs_source_label,
    finalize_config,
    main,
    parse_args,
    parse_model_config,
    prepare_docs_access,
    prepare_production_profiles,
    production_job,
    run_benchmark_key,
    run_benchmark_variant,
    stage_filtered_config,
    stage_pinned_docs_task,
    uses_live_mcp_eval,
    versioned_name,
)


def base_config() -> dict[str, Any]:
    return {"agents": [{"name": "oracle"}], "datasets": []}


class RunBenchmarkTest(unittest.TestCase):
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
            [{"path": "tasks/mpp", "task_names": ["server-*"]}],
        )

    def test_finalize_config_selects_tempo_mcp_suite(self) -> None:
        self.assertEqual(
            finalize_config(base_config(), {"task_suite": "tempo-mcp"})["datasets"],
            [{"path": "tasks/tempo-mcp-v1"}],
        )

    def test_tempo_mcp_suite_uses_the_live_mcp_server(self) -> None:
        self.assertTrue(uses_live_mcp_eval({"task_suite": "tempo-mcp"}))
        self.assertFalse(uses_live_mcp_eval({"task_suite": "tempo"}))

    def test_tempo_profiles_prepare_distinct_docs_access(self) -> None:
        pinned = {"mode": "pinned", "repo": "tempo/docs", "sha": "docs123"}
        with (
            patch("scripts.run_benchmark.docs_source", return_value=pinned),
            patch(
                "scripts.run_benchmark.ensure_docs_bundle", return_value="docs-bundle"
            ) as ensure_bundle,
        ):
            self.assertEqual(
                prepare_docs_access({"task_suite": "tempo", "profile": "docs"}),
                (pinned, "docs-bundle"),
            )
            self.assertEqual(
                prepare_docs_access({"task_suite": "tempo", "profile": "mcp"}),
                ({"mode": "live"}, None),
            )

        ensure_bundle.assert_called_once_with(pinned)
        self.assertEqual(docs_source_label(pinned), "docs123")
        self.assertEqual(docs_source_label({"mode": "live"}), "live")

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

    def test_production_variant_accepts_explicit_mcp_profile(self) -> None:
        options = {
            "env_file": None,
            "job_name": "production-mcp-test",
            "profile": "mcp",
            "sync": False,
            "task_suite": "tempo",
        }
        with (
            patch("scripts.run_benchmark.load_env_file"),
            patch("scripts.run_benchmark.preflight"),
            patch("scripts.run_benchmark.preflight_mcp_target"),
            patch("scripts.run_benchmark.docs_source") as docs_source,
            patch("scripts.run_benchmark.ensure_docs_bundle") as ensure_bundle,
            patch("scripts.run_benchmark.run_production_variant") as run_production,
            patch("scripts.run_benchmark.run") as run,
        ):
            run_benchmark_variant("production-daytona", options)

        docs_source.assert_not_called()
        ensure_bundle.assert_not_called()
        run_production.assert_called_once_with(
            "production-mcp-test", options, {"mode": "live"}, None
        )
        run.assert_not_called()

    def test_production_all_profile_runs_docs_and_mcp_jobs(self) -> None:
        with (
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
                    "--job-name",
                    "paired-run",
                ]
            )

        prepare.assert_called_once()
        profiles = {
            invocation.args[1]["profile"]: invocation.args[1]
            for invocation in run_variant.call_args_list
        }
        self.assertEqual(set(profiles), {"docs", "mcp"})
        self.assertEqual(profiles["docs"]["job_name"], "paired-run-docs")
        self.assertEqual(profiles["mcp"]["job_name"], "paired-run-mcp")
        self.assertTrue(all(not options["sync"] for options in profiles.values()))
        self.assertTrue(
            all(options["pair_id"] == "paired-run" for options in profiles.values())
        )

    def test_dev_and_production_model_configs_are_distinct(self) -> None:
        dev = parse_model_config("config/models.dev.yaml", None)
        production = parse_model_config("config/models.production.yaml", None)

        self.assertEqual(
            [model["model_name"] for model in dev["models"]],
            ["claude-haiku-4-5-20251001"],
        )
        self.assertEqual(
            [model["model_name"] for model in production["models"]],
            [
                "claude-haiku-4-5-20251001",
                "claude-sonnet-5",
                "gpt-5.4-mini-2026-03-17",
                "gpt-5.4-2026-03-05",
            ],
        )
        self.assertEqual([model["n_concurrent"] for model in dev["models"]], ["16"])
        self.assertEqual(
            [model["n_concurrent"] for model in production["models"]],
            ["16", "16", "16", "16"],
        )

    def test_production_profiles_prepare_shared_inputs_once(self) -> None:
        source = {"mode": "pinned", "repo": "tempo/docs", "sha": "docs123"}
        options = {
            "agent_concurrency": None,
            "env_file": None,
            "models_config": "config/models.dev.yaml",
            "profile": "all",
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
                {"path": "tasks/mpp", "task_names": ["server-*"]},
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

    def test_benchmark_provenance_uses_versioned_dataset_identity(self) -> None:
        self.assertEqual(
            benchmark_provenance("tempo"),
            [{"id": "tempo-bench-v1", "dataset": "tempo/tempo-bench-v1"}],
        )

    def test_run_names_resolve_from_catalog(self) -> None:
        self.assertEqual(
            versioned_name(BenchmarkKey.TEMPO, "oracle-local"),
            "tempo-bench-v1-oracle-local",
        )
        self.assertEqual(
            run_benchmark_key({"benchmark": "tempo"}, "mpp"), BenchmarkKey.MPP
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

    def test_production_job_uses_requested_attempts(self) -> None:
        model_config = {
            "models": [
                {
                    "agent": "claude-code",
                    "model_name": "claude-haiku-4-5",
                    "n_concurrent": None,
                    "concurrency_group": None,
                }
            ]
        }

        self.assertEqual(
            production_job("test-run", model_config, {"n_attempts": "1"})["n_attempts"],
            1,
        )
        self.assertEqual(
            production_job("test-run", model_config, {})["n_attempts"],
            3,
        )

    def test_mcp_profile_is_injected_at_job_level(self) -> None:
        config = {
            "agents": [
                {"name": "claude-code"},
                {"name": "codex"},
                {"name": "oracle"},
            ]
        }

        agents = apply_profile(config, "mcp")["agents"]
        expected_server = [
            {
                "name": "tempo",
                "transport": "streamable-http",
                "url": "https://mcp.tempo.xyz/",
            }
        ]

        self.assertEqual(
            [(agent["name"], agent.get("mcp_servers")) for agent in agents],
            [
                ("claude-code", expected_server),
                ("codex", expected_server),
                ("oracle", None),
            ],
        )

    def test_mcp_eval_profiles_inject_distinct_bridge_servers(self) -> None:
        self.assertEqual(
            apply_profile({"agents": [{"name": "claude-code"}]}, "mcp-direct")[
                "agents"
            ][0]["mcp_servers"],
            MCP_DIRECT_PROFILE["mcp_servers"],
        )
        self.assertEqual(
            apply_profile({"agents": [{"name": "claude-code"}]}, "mcp-code")["agents"][
                0
            ]["mcp_servers"],
            MCP_CODE_PROFILE["mcp_servers"],
        )

    def test_pair_id_is_injected_for_non_oracle_agents(self) -> None:
        self.assertEqual(
            apply_pair_id(
                {"agents": [{"name": "claude-code"}, {"name": "oracle"}]},
                "pair-1",
            ),
            {
                "agents": [
                    {"name": "claude-code", "env": {"TEMPO_BENCH_PAIR_ID": "pair-1"}},
                    {"name": "oracle"},
                ]
            },
        )

    def test_daytona_base_image_uses_the_supplied_image(self) -> None:
        self.assertEqual(
            daytona_base_image({"base_image": "ghcr.io/tempoxyz/base:source-test"}),
            "ghcr.io/tempoxyz/base:source-test",
        )

    def test_daytona_base_image_requires_an_explicit_image(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "requires --base-image"):
            daytona_base_image({})

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

    def test_staged_pinned_docs_keep_the_public_hostname(self) -> None:
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
                "/usr/local/share/ca-certificates/tempo-bench-docs.crt",
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
            self.assertIn("DNS:tempo.xyz", certificate.stdout)
            self.assertIn(
                "- docs.tempo.xyz",
                (environment_dir / "docker-compose.yaml").read_text(),
            )
            self.assertIn(
                "- tempo.xyz",
                (environment_dir / "docker-compose.yaml").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
