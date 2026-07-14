from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZERO_REWARD = {"correctness": 0, "quality": 0, "reward": 0}


class TempoRewardSchemaTest(unittest.TestCase):
    def test_every_gated_failure_emits_the_complete_reward_schema(self) -> None:
        scripts = sorted(ROOT.glob("tasks/tempo-v1/*/tests/test.sh"))
        self.assertTrue(scripts)

        for script in scripts:
            for failure in ("workspace", "verifier", "rewardkit"):
                with self.subTest(task=script.parents[1].name, failure=failure):
                    self._assert_gated_failure(script, failure)

    def _assert_gated_failure(self, script: Path, failure: str) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            workspace = temporary / "workspace"
            tests = temporary / "tests"
            verifier = tests / "correctness" / "verify-tempo.sh"
            logs = temporary / "logs"

            tests.joinpath("correctness").mkdir(parents=True)
            verifier.write_text(
                "#!/usr/bin/env bash\nexit "
                + ("1" if failure == "verifier" else "0")
                + "\n"
            )
            if failure != "workspace":
                workspace.mkdir()

            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)
            env.update(
                {
                    "TEMPO_BENCH_LOG_DIR": str(logs),
                    "TEMPO_BENCH_TESTS_DIR": str(tests),
                    "TEMPO_BENCH_WORKSPACE": str(workspace),
                    "tempo_bench_rewardkit_VENV": str(temporary / "missing-venv"),
                }
            )
            result = subprocess.run(
                ["bash", str(script)],
                check=False,
                capture_output=True,
                env=env,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads((logs / "reward.json").read_text()),
                ZERO_REWARD,
            )


if __name__ == "__main__":
    unittest.main()
