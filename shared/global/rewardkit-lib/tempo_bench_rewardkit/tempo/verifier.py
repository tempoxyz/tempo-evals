from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tempo_bench_rewardkit.common.tempo_reward import (
    ZERO_REWARD,
    write_correctness_gate,
    write_reward,
)


def _run_rewardkit(tests: Path, workspace: Path, output: Path) -> bool:
    return (
        subprocess.run(
            [
                sys.executable,
                "-m",
                "rewardkit",
                str(tests),
                "--workspace",
                str(workspace),
                "--output",
                str(output),
            ],
            check=False,
        ).returncode
        == 0
    )


def run() -> int:
    log_dir = Path(os.environ.get("TEMPO_BENCH_LOG_DIR", "/logs/verifier"))
    workspace = Path(os.environ.get("TEMPO_BENCH_WORKSPACE", "/app"))
    tests = Path(os.environ.get("TEMPO_BENCH_TESTS_DIR", "/tests"))
    reward = log_dir / "reward.json"
    details = log_dir / "reward-details.json"
    correctness_output = log_dir / "correctness-reward.json"
    rewardkit_output = log_dir / "rewardkit-output.json"

    log_dir.mkdir(parents=True, exist_ok=True)
    for path in (reward, details, correctness_output, rewardkit_output):
        path.unlink(missing_ok=True)

    def verifier_error(message: str) -> int:
        print(message, file=sys.stderr)
        for path in (reward, details, correctness_output, rewardkit_output):
            path.unlink(missing_ok=True)
        return 1

    with (
        tempfile.TemporaryDirectory() as workspace_dir,
        tempfile.TemporaryDirectory() as correctness_dir,
    ):
        rewardkit_workspace = Path(workspace_dir)
        try:
            shutil.copytree(workspace, rewardkit_workspace, dirs_exist_ok=True)
        except OSError as error:
            return verifier_error(f"Could not copy verifier workspace: {error}")

        verifier_result = subprocess.run(
            ["bash", str(tests / "correctness" / "verify-tempo.sh")], check=False
        )
        if verifier_result.returncode != 0:
            if (log_dir / "tempo-bench-scores.json").is_file():
                reward.write_text(f"{json.dumps(ZERO_REWARD)}\n")
                return 0
            return verifier_result.returncode or 1

        correctness_tests = Path(correctness_dir) / "correctness"
        try:
            shutil.copytree(tests / "correctness", correctness_tests)
        except OSError as error:
            return verifier_error(f"Could not stage correctness tests: {error}")
        if not _run_rewardkit(
            Path(correctness_dir), rewardkit_workspace, correctness_output
        ):
            return verifier_error("RewardKit correctness checks failed to run.")
        try:
            write_correctness_gate(correctness_output, reward)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return verifier_error(f"Invalid RewardKit correctness output: {error}")
        correctness_output.unlink(missing_ok=True)
        if reward.is_file():
            return 0

        quality_config = tests / "quality" / "reward.toml"
        if not quality_config.is_file():
            return verifier_error(f"Missing quality configuration: {quality_config}")
        if not _run_rewardkit(tests, rewardkit_workspace, rewardkit_output):
            return verifier_error("RewardKit quality grading failed to run.")
        try:
            write_reward(rewardkit_output, reward)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            return verifier_error(f"Invalid RewardKit output: {error}")
        rewardkit_output.unlink(missing_ok=True)
        return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
