# SYNCED FROM shared/rewardkit/quality/check.py
# BY npm run sync. DO NOT EDIT COPIES IN tasks/.
import rewardkit as rk
import tempo_bench_rewardkit  # noqa: F401

rk.agent_turn_efficiency()
rk.agent_token_efficiency()

rk.tempo_mcp_tool_used("tempo")
