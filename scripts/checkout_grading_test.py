from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from shared.checkout.tests.grade import efficiency_metrics, run

ROOT = Path(__file__).resolve().parents[1]
BASELINE = {"turns": 10, "tools": 10, "time": 60}


def trajectory(turns: int = 10, seconds: int = 60) -> dict:
    start = datetime(2026, 10, 20, tzinfo=UTC)
    return {
        "steps": [
            {"source": "user", "timestamp": start.isoformat()},
            *[
                {
                    "source": "agent",
                    "tool_calls": [{"function_name": "browser_click"}],
                    "timestamp": (
                        start + timedelta(seconds=seconds * (index + 1) / turns)
                    ).isoformat(),
                }
                for index in range(turns)
            ],
        ]
    }


class CheckoutGradingTest(unittest.TestCase):
    def test_each_extra_baseline_halves_quality_at_weight_one(self) -> None:
        at_baseline = efficiency_metrics(trajectory(), 0, BASELINE)
        self.assertEqual(at_baseline["quality"], 1)
        self.assertEqual(at_baseline["excess"], {"turns": 0, "tools": 0, "time": 0})
        # Twice the baseline on every metric is one doubling of total weight 1.
        self.assertEqual(
            efficiency_metrics(trajectory(20, 120), 0, BASELINE)["quality"], 0.5
        )
        self.assertAlmostEqual(
            efficiency_metrics(trajectory(20), 0, BASELINE)["quality"], 2**-0.7, 6
        )
        self.assertAlmostEqual(
            efficiency_metrics(trajectory(seconds=120), 0, BASELINE)["quality"],
            2**-0.3,
            6,
        )
        # Each retry quarters quality; beating the baseline earns no bonus.
        self.assertEqual(efficiency_metrics(trajectory(), 1, BASELINE)["quality"], 0.25)
        self.assertEqual(
            efficiency_metrics(trajectory(5, 30), 0, BASELINE)["quality"], 1
        )

    def test_all_tool_calls_including_errors_are_charged(self) -> None:
        data = trajectory()
        data["steps"][1]["tool_calls"] *= 6
        data["steps"].append(
            {"source": "agent", "is_copied_context": True, "tool_calls": [{}] * 100}
        )
        metrics = efficiency_metrics(data, 0, BASELINE)
        self.assertEqual(metrics["tool_calls"], 15)
        self.assertEqual(metrics["excess"]["tools"], 0.5)
        self.assertLess(metrics["quality"], 1)

    def test_null_tool_calls_are_empty_but_malformed_values_are_rejected(self) -> None:
        data = trajectory()
        data["steps"][1]["tool_calls"] = None
        self.assertEqual(efficiency_metrics(data, 0, BASELINE)["tool_calls"], 9)
        for malformed in (False, {}, "", [None]):
            data["steps"][1]["tool_calls"] = malformed
            with (
                self.subTest(calls=malformed),
                self.assertRaisesRegex(ValueError, "invalid_tool_calls"),
            ):
                efficiency_metrics(data, 0, BASELINE)

    def test_missing_telemetry_is_not_a_perfect_score(self) -> None:
        for data, attempts in (
            (None, 0),
            (trajectory(), None),
            ({"steps": [{"source": "agent"}]}, 0),
        ):
            with (
                self.subTest(data=data, attempts=attempts),
                self.assertRaises(ValueError),
            ):
                efficiency_metrics(data, attempts, BASELINE)

    def test_native_rewards_with_real_rewardkit(self) -> None:
        for passed, data, attempts, expected_quality, baseline in (
            (True, trajectory(), 0, 1, BASELINE),
            (True, trajectory(20, 120), 0, 0.5, BASELINE),
            (True, trajectory(), 1, 0.25, BASELINE),
            (False, trajectory(20, 360), 2, 0, BASELINE),
            (False, trajectory(), None, 0, BASELINE),
            (False, None, None, 0, BASELINE),
            (True, trajectory(), None, None, BASELINE),
            (True, None, 0, None, BASELINE),
            # Calibration runs: no baseline, so no quality, but raw metrics.
            (True, trajectory(), 0, None, None),
        ):
            with (
                self.subTest(passed=passed, quality=expected_quality, baseline=baseline),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                tests = root / "tests"
                tests.mkdir()
                if baseline:
                    (tests / "efficiency_baseline.json").write_text(json.dumps(baseline))
                shutil.copytree(
                    ROOT / "shared/checkout/tests/quality", tests / "quality"
                )
                (tests / "check.py").write_text(
                    "import json, os\nfrom pathlib import Path\n"
                    "log = Path(os.environ['STABLE_BENCH_LOG_DIR'])\n"
                    f"payment = {{'reward': {int(passed)}}}\n"
                    "(log/'reward.json').write_text(json.dumps(payment))\n"
                    f"details = {{'extra_checkout_attempts': {attempts!r}}}\n"
                    "(log/'details.json').write_text(json.dumps(details))\n"
                )
                trajectory_path = root / "trajectory.json"
                if data is not None:
                    trajectory_path.write_text(json.dumps(data))
                log = root / "logs"
                with patch.dict(
                    os.environ,
                    {
                        "STABLE_BENCH_LOG_DIR": str(log),
                        "STABLE_BENCH_WORKSPACE": str(root),
                    },
                ):
                    run(tests, log, trajectory_path)
                rewards = json.loads((log / "reward.json").read_text())
                self.assertEqual(rewards["reward"], int(passed))
                self.assertEqual(rewards["correctness"], int(passed))
                self.assertEqual(rewards.get("quality"), expected_quality)
                metrics = json.loads((log / "efficiency.json").read_text())
                if data:
                    self.assertGreater(metrics["model_turns"], 0)
                    self.assertEqual(metrics.get("extra_checkout_attempts"), attempts)
                    if baseline is None:
                        self.assertNotIn("quality", metrics)
                    self.assertGreater(metrics["trajectory_duration_sec"], 0)
                if not passed:
                    self.assertFalse((log / "rewardkit-output.json").exists())
                if expected_quality and data:
                    self.assertTrue((log / "rewardkit-output.json").is_file())


class CheckoutBaselinesTest(unittest.TestCase):
    def test_each_metric_takes_its_own_passing_minimum(self) -> None:
        from scripts.checkout_baselines import baselines

        with tempfile.TemporaryDirectory() as temporary:
            job = Path(temporary)
            for index, (task, correct, turns, tools, seconds) in enumerate(
                (
                    ("checkout-v2/a-directed", 1, 12, 9, 40.5),
                    ("checkout-v2/a-directed", 1, 8, 14, 55.0),
                    ("checkout-v2/a-directed", 0, 2, 2, 5.0),
                    ("checkout-v2/b-directed", 0, 5, 5, 20.0),
                )
            ):
                trial = job / f"t{index}"
                (trial / "verifier").mkdir(parents=True)
                (trial / "result.json").write_text(json.dumps({"task_name": task}))
                (trial / "verifier/reward.json").write_text(
                    json.dumps({"correctness": correct})
                )
                (trial / "verifier/efficiency.json").write_text(
                    json.dumps(
                        {
                            "model_turns": turns,
                            "tool_calls": tools,
                            "trajectory_duration_sec": seconds,
                        }
                    )
                )
            self.assertEqual(
                baselines([job]),
                {"a-directed": {"turns": 8, "tools": 9, "time": 40.5}},
            )


if __name__ == "__main__":
    unittest.main()
