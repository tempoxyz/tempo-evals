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
    MCP_PROFILE,
    BenchmarkKey,
    apply_profile,
    benchmark_provenance,
    daytona_base_image,
    finalize_config,
    parse_args,
    run_benchmark_key,
    stage_filtered_config,
    stage_pinned_docs_task,
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
                'TEMPO_RPC_URL = "http://tempo-localnet:8545"\n'
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
                    "-ext",
                    "subjectAltName",
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
