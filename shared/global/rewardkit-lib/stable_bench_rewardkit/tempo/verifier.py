from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from stable_bench_rewardkit.common.tempo_reward import (
    ZERO_REWARD,
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
    log_dir = Path(os.environ.get("STABLE_BENCH_LOG_DIR", "/logs/verifier"))
    workspace = Path(os.environ.get("STABLE_BENCH_WORKSPACE", "/app"))
    tests = Path(os.environ.get("STABLE_BENCH_TESTS_DIR", "/tests"))
    reward = log_dir / "reward.json"
    details = log_dir / "reward-details.json"
    rewardkit_output = log_dir / "rewardkit-output.json"

    log_dir.mkdir(parents=True, exist_ok=True)
    for path in (reward, details, rewardkit_output):
        path.unlink(missing_ok=True)

    def verifier_error(message: str) -> int:
        print(message, file=sys.stderr)
        for path in (reward, details, rewardkit_output):
            path.unlink(missing_ok=True)
        return 1

    with tempfile.TemporaryDirectory() as workspace_dir:
        rewardkit_workspace = Path(workspace_dir)
        try:
            shutil.copytree(workspace, rewardkit_workspace, dirs_exist_ok=True)
        except OSError as error:
            return verifier_error(f"Could not copy verifier workspace: {error}")

        verifier_result = subprocess.run(
            ["bash", str(tests / "correctness" / "verify-tempo.sh")], check=False
        )
        if verifier_result.returncode != 0:
            if (log_dir / "stable-bench-scores.json").is_file():
                reward.write_text(f"{json.dumps(ZERO_REWARD)}\n")
                return 0
            return verifier_result.returncode or 1

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
