from __future__ import annotations

import unittest
from typing import Any

from scripts.run_benchmark import finalize_config


def base_config() -> dict[str, Any]:
    return {"agents": [{"name": "oracle"}], "datasets": []}


class RunBenchmarkTest(unittest.TestCase):
    def test_finalize_config_defaults_to_tempo_suite(self) -> None:
        config = finalize_config(base_config(), {})

        self.assertEqual(
            config["datasets"],
            [
                {
                    "path": "tasks/tempo",
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
                    "path": "tasks/tempo",
                    "task_names": ["*-base", "*-docs", "*-mcp"],
                },
                {"path": "tasks/mpp", "task_names": ["server-*"]},
            ],
        )


if __name__ == "__main__":
    unittest.main()
