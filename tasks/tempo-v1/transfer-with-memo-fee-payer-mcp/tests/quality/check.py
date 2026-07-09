# SYNCED FROM shared/global/rewardkit/quality/check.py
# BY npm run sync. DO NOT EDIT COPIES IN tasks/.
from pathlib import Path

import rewardkit as rk
from tempo_bench_rewardkit.common.checks import (
    TokenEfficiencyConfig,
    register_token_efficiency_check,
)

trajectory_path = Path("/logs/agent/trajectory.json")
if trajectory_path.exists():
    rk.trajectory_turn_count(max_turns=20, path=str(trajectory_path))
    register_token_efficiency_check(TokenEfficiencyConfig())
