import rewardkit as rk
import tempo_bench_rewardkit

rk.tempo_typescript_project()
rk.tempo_source_patterns(
    [
        {
            "name": "source_calls_set_user_token",
            "pattern": r"setUserToken",
        },
        {
            "name": "source_reads_tempo_fee_token",
            "pattern": r"TEMPO_FEE_TOKEN",
        },
    ]
)
rk.tempo_onchain_verifier()

rk.tempo_trajectory_matches(
    r"tempo|mcp|docs|documentation|search",
)
