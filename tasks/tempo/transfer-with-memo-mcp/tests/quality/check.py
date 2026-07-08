# SYNCED FROM shared/tempo-testnet/tests/quality/check.py
# BY npm run sync. DO NOT EDIT COPIES IN tasks/.
import rewardkit as rk
from tempo_bench_rewardkit.common.checks import (
    TokenEfficiencyConfig,
    register_token_efficiency_check,
)

rk.trajectory_turn_count(max_turns=20)
register_token_efficiency_check(
    TokenEfficiencyConfig(
        thresholds=[
            [250000, 1.0],
            [500000, 0.8],
            [1000000, 0.5],
            [1500000, 0.2],
            ["*", 0.0],
        ],
    )
)

rk.tempo_mcp_tool_used("tempo")
