from __future__ import annotations

import unittest
from typing import Any

from scripts.run_benchmark import (
    BenchmarkKey,
    benchmark_provenance,
    finalize_config,
    run_benchmark_key,
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
                    "task_names": ["*-base", "*-docs", "*-mcp"],
                }
            ],
        )

    def test_finalize_config_selects_mpp_suite(self) -> None:
        config = finalize_config(base_config(), {"task_suite": "mpp"})

        self.assertEqual(
            config["datasets"],
            [{"path": "tasks/mpp", "task_names": ["server-*"]}],
        )

    def test_finalize_config_requires_all_suite_for_full_matrix(self) -> None:
        config = finalize_config(base_config(), {"task_suite": "all"})

        self.assertEqual(
            config["datasets"],
            [
                {
                    "path": "tasks/tempo-v1",
                    "task_names": ["*-base", "*-docs", "*-mcp"],
                },
                {"path": "tasks/mpp", "task_names": ["server-*"]},
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


if __name__ == "__main__":
    unittest.main()
