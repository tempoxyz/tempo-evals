import rewardkit as rk
import tempo_bench_rewardkit

rk.tempo_typescript_project()
rk.tempo_source_patterns(
    [
        {
            "name": "source_reads_multi_recipients",
            "pattern": r"TEMPO_MULTI_RECIPIENTS",
        },
        {
            "name": "source_reads_multi_amounts",
            "pattern": r"TEMPO_MULTI_AMOUNTS",
        },
        {
            "name": "source_builds_transfer_calls",
            "pattern": r"encodeFunctionData|transfer\.call",
        },
        {
            "name": "source_sends_multiple_calls",
            "pattern": r"sendTransaction\([\s\S]*calls",
        },
    ]
)
rk.tempo_onchain_verifier()

rk.tempo_trajectory_matches(
    r"tempo|mcp|docs|documentation|search",
)
