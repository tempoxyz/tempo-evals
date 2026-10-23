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
    def test_each_efficiency_metric_penalizes_extra_work(self) -> None:
        self.assertEqual(
            efficiency_metrics(trajectory(), 0)["scores"],
            {"turns": 0.5, "tools": 0.6, "retries": 1, "time": 0.5},
        )
        self.assertEqual(
            efficiency_metrics(trajectory(20), 0)["scores"]["turns"], 1 / 3
        )
        self.assertEqual(efficiency_metrics(trajectory(), 1)["scores"]["retries"], 0.5)
        self.assertEqual(
            efficiency_metrics(trajectory(seconds=120), 0)["scores"]["time"], 1 / 3
        )

    def test_all_tool_calls_including_errors_are_charged(self) -> None:
        data = trajectory()
        baseline = efficiency_metrics(data, 0)
        data["steps"][1]["tool_calls"] *= 6
        data["steps"].append(
            {"source": "agent", "is_copied_context": True, "tool_calls": [{}] * 100}
        )
        metrics = efficiency_metrics(data, 0)
        self.assertEqual(metrics["tool_calls"], 15)
        self.assertEqual(metrics["scores"]["tools"], 0.5)
        self.assertLess(metrics["scores"]["tools"], baseline["scores"]["tools"])
        self.assertEqual(efficiency_metrics(trajectory(), 2)["scores"]["retries"], 0.25)

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
                efficiency_metrics(data, attempts)

    def test_native_rewards_with_real_rewardkit(self) -> None:
        for passed, data, attempts, expected_quality in (
            (True, trajectory(), 0, 0.63),
            (True, trajectory(20, 120), 0, 0.4952),
            (False, trajectory(20, 360), 2, 0),
            (False, trajectory(), None, 0),
            (False, None, None, 0),
            (True, trajectory(), None, None),
            (True, None, 0, None),
        ):
            with (
                self.subTest(passed=passed, quality=expected_quality),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                tests = root / "tests"
                tests.mkdir()
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
                    self.assertGreater(metrics["trajectory_duration_sec"], 0)
                if not passed:
                    self.assertFalse((log / "rewardkit-output.json").exists())
                if expected_quality and data:
                    self.assertTrue((log / "rewardkit-output.json").is_file())


if __name__ == "__main__":
    unittest.main()
