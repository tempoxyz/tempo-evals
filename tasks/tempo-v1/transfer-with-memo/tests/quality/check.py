from pathlib import Path

import rewardkit as rk
from stable_bench_rewardkit.common.checks import (
    TokenEfficiencyConfig,
    register_token_efficiency_check,
)

trajectory_paths = (Path("/logs/agent/trajectory.json"), Path("/logs/trajectory.json"))
trajectory_path = next((path for path in trajectory_paths if path.exists()), None)
if trajectory_path is not None:
    rk.trajectory_turn_count(max_turns=20, path=str(trajectory_path))
    register_token_efficiency_check(TokenEfficiencyConfig())
