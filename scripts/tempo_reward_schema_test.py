from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZERO_REWARD = {"correctness": 0, "quality": 0, "reward": 0}


class RewardSchemaTest(unittest.TestCase):
    def test_every_tempo_gated_failure_emits_the_complete_reward_schema(
        self,
    ) -> None:
        scripts = sorted(ROOT.glob("tasks/tempo-v1/*/tests/test.sh"))
        self.assertTrue(scripts)

        for script in scripts:
            for failure in ("workspace", "verifier", "rewardkit"):
                with self.subTest(task=script.parents[1].name, failure=failure):
                    self._assert_tempo_gated_failure(script, failure)

    def test_every_mpp_missing_rewardkit_failure_emits_the_complete_reward_schema(
        self,
    ) -> None:
        scripts = sorted(ROOT.glob("tasks/mpp/*/tests/test.sh"))
        self.assertTrue(scripts)

        for script in scripts:
            with self.subTest(task=script.parents[1].name):
                self._assert_mpp_missing_rewardkit_failure(script)

    def test_mpp_binary_fallback_emits_the_complete_reward_schema(self) -> None:
        verifier_utils = (
            ROOT
            / "shared/global/rewardkit-lib/tempo_bench_rewardkit/mpp/verifier_utils.py"
        )
        for score in (0, 1):
            with self.subTest(score=score), tempfile.TemporaryDirectory() as temporary:
                temporary_path = Path(temporary)
                details = temporary_path / "details.json"
                scores = temporary_path / "scores.json"
                rewardkit_output = temporary_path / "rewardkit-output.json"
                reward = temporary_path / "reward.json"
                scores.write_text(json.dumps({"reward": score}))

                result = subprocess.run(
                    [
                        sys.executable,
                        str(verifier_utils),
                        "write-binary-reward",
                        str(details),
                        str(scores),
                        str(rewardkit_output),
                        str(reward),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    json.loads(reward.read_text()),
                    {"correctness": score, "quality": 0, "reward": score},
                )

    def test_mpp_final_reward_preserves_native_dimension_scores(self) -> None:
        verifier_utils = (
            ROOT
            / "shared/global/rewardkit-lib/tempo_bench_rewardkit/mpp/verifier_utils.py"
        )
        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            details = temporary_path / "details.json"
            scores = temporary_path / "scores.json"
            rewardkit_output = temporary_path / "rewardkit-output.json"
            reward = temporary_path / "reward.json"
            scores.write_text(json.dumps({"reward": 1}))
            rewardkit_output.write_text(
                json.dumps({"correctness": 0.75, "quality": 0.6, "reward": 0.7})
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(verifier_utils),
                    "write-binary-reward",
                    str(details),
                    str(scores),
                    str(rewardkit_output),
                    str(reward),
                ],
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(reward.read_text()),
                {"correctness": 0.75, "quality": 0.6, "reward": 1},
            )

    def _assert_tempo_gated_failure(self, script: Path, failure: str) -> None:
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

    def _assert_mpp_missing_rewardkit_failure(self, script: Path) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            workspace = temporary / "workspace"
            tests = temporary / "tests"
            logs = temporary / "logs"
            workspace.mkdir()
            tests.mkdir()

            env = os.environ.copy()
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
