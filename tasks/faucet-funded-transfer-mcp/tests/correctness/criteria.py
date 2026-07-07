import rewardkit as rk
import tempo_bench_rewardkit

rk.tempo_typescript_project()
rk.tempo_source_patterns(
    [
        {
            "name": "source_calls_faucet_fund",
            "pattern": r"faucet\.fundSync|fundSync",
        },
        {
            "name": "source_reads_faucet_private_key",
            "pattern": r"TEMPO_FAUCET_PRIVATE_KEY",
        },
        {
            "name": "source_sends_transfer",
            "pattern": r"transferSync|transferWithMemo",
        },
    ]
)
rk.tempo_onchain_verifier()

rk.tempo_mcp_tool_used("tempo")
