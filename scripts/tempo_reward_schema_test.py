from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared" / "global" / "rewardkit-lib"))

from tempo_bench_rewardkit.common.tempo_reward import compose_reward  # noqa: E402

ZERO_REWARD = {"correctness": 0, "quality": 0, "reward": 0}


class RewardSchemaTest(unittest.TestCase):
    def test_every_tempo_verifier_uses_the_shared_wrapper(self) -> None:
        scripts = sorted(ROOT.glob("tasks/tempo-v1/*/tests/test.sh"))
        self.assertEqual(len(scripts), 9)
        contents = {script.read_text() for script in scripts}
        self.assertEqual(len(contents), 1)
        wrapper = contents.pop()
        self.assertLessEqual(len(wrapper.splitlines()), 9)
        self.assertIn("tempo_bench_rewardkit.tempo.verifier", wrapper)

    def test_tempo_reward_combines_code_and_aggregate_quality(self) -> None:
        for code_score, aggregate_quality, quality, reward in (
            (0, 0, 0, 0.5),
            (0, 1, 0.5, 0.75),
            (0.6, 0.8, 0.7, 0.85),
            (1, 1, 1, 1),
        ):
            with self.subTest(
                code_score=code_score, aggregate_quality=aggregate_quality
            ):
                self.assertEqual(
                    compose_reward(
                        {
                            "correctness": code_score,
                            "quality": aggregate_quality,
                            "reward": 0.123,
                        }
                    ),
                    {"correctness": 1, "quality": quality, "reward": reward},
                )
        with self.assertRaises(ValueError):
            compose_reward({"correctness": 1, "reward": 1})

    def test_tempo_functional_failure_emits_zero(self) -> None:
        result, reward, _ = self._run_tempo(
            'printf \'{"reward":0}\\n\' > "$TEMPO_BENCH_LOG_DIR/'
            'tempo-bench-scores.json"\nexit 1\n'
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(reward, ZERO_REWARD)

    def test_tempo_verifier_error_does_not_emit_a_reward(self) -> None:
        result, reward, _ = self._run_tempo("exit 1\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(reward)

    def test_tempo_static_failure_contributes_to_quality(self) -> None:
        quality_check = (
            "import os\nfrom pathlib import Path\nimport rewardkit as rk\n"
            "@rk.criterion\ndef quality(workspace: Path) -> float:\n"
            '    Path(os.environ["TEMPO_TEST_QUALITY_MARKER"]).touch()\n'
            "    return 1\n"
        )
        result, reward, quality_ran = self._run_tempo(
            "exit 0\n",
            correctness=0,
            quality_config='[scoring]\naggregation = "weighted_mean"\n',
            quality_check=quality_check,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(reward, {"correctness": 1, "quality": 0.5, "reward": 0.75})
        self.assertTrue(quality_ran)

    def test_tempo_missing_quality_config_is_a_verifier_error(self) -> None:
        result, reward, _ = self._run_tempo(
            "exit 0\n",
            correctness=1,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(reward)
        self.assertIn("Missing quality configuration", result.stderr)

    def test_tempo_quality_config_failure_is_a_verifier_error(self) -> None:
        result, reward, _ = self._run_tempo(
            "exit 0\n",
            correctness=1,
            quality_config="[judge\n",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(reward)

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

    def _run_tempo(
        self,
        verifier_body: str,
        *,
        correctness: float | None = None,
        quality_config: str | None = None,
        quality_check: str | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, float] | None, bool]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary = Path(temporary_directory)
            workspace = temporary / "workspace"
            tests = temporary / "tests"
            verifier = tests / "correctness" / "verify-tempo.sh"
            logs = temporary / "logs"
            marker = temporary / "quality-ran"

            workspace.mkdir()
            tests.joinpath("correctness").mkdir(parents=True)
            verifier.write_text(f"#!/usr/bin/env bash\n{verifier_body}")
            if correctness is not None:
                tests.joinpath("correctness", "criteria.py").write_text(
                    "from pathlib import Path\nimport rewardkit as rk\n"
                    "@rk.criterion\n"
                    "def static_gate(workspace: Path) -> float:\n"
                    f"    return {correctness!r}\n"
                )
            if quality_config is not None or quality_check is not None:
                tests.joinpath("quality").mkdir()
            if quality_config is not None:
                tests.joinpath("quality", "reward.toml").write_text(quality_config)
            if quality_check is not None:
                tests.joinpath("quality", "check.py").write_text(quality_check)

            env = os.environ.copy()
            env.pop("ANTHROPIC_API_KEY", None)
            env.pop("REWARDKIT_JUDGE", None)
            env.update(
                {
                    "PYTHONPATH": str(ROOT / "shared/global/rewardkit-lib"),
                    "TEMPO_BENCH_LOG_DIR": str(logs),
                    "TEMPO_BENCH_TESTS_DIR": str(tests),
                    "TEMPO_BENCH_WORKSPACE": str(workspace),
                    "TEMPO_TEST_QUALITY_MARKER": str(marker),
                    "tempo_bench_rewardkit_VENV": sys.prefix,
                }
            )
            result = subprocess.run(
                [
                    "bash",
                    str(sorted(ROOT.glob("tasks/tempo-v1/*/tests/test.sh"))[0]),
                ],
                check=False,
                capture_output=True,
                env=env,
                text=True,
            )
            reward_path = logs / "reward.json"
            return (
                result,
                json.loads(reward_path.read_text()) if reward_path.is_file() else None,
                marker.is_file(),
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
