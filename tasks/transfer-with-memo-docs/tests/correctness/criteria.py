import rewardkit as rk
import tempo_bench_rewardkit

rk.tempo_typescript_project()
rk.tempo_source_patterns(
    [
        {
            "name": "source_uses_transfer_with_memo_semantics",
            "pattern": r"transferWithMemo|transferSync",
        },
        {
            "name": "source_reads_tempo_memo",
            "pattern": r"TEMPO_MEMO",
        },
        {
            "name": "source_parses_token_units",
            "pattern": r"parseUnits",
        },
    ]
)
rk.tempo_onchain_verifier()

rk.tempo_trajectory_matches(
    r"docs\.tempo\.xyz|TEMPO_DOCS_URL|Tempo docs|documentation",
)
