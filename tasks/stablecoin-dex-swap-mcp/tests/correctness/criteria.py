import rewardkit as rk
import tempo_bench_rewardkit

rk.tempo_typescript_project()
rk.tempo_source_patterns(
    [
        {
            "name": "source_uses_dex_actions",
            "pattern": r"Actions\.dex|\.dex\.",
        },
        {
            "name": "source_approves_dex_spending",
            "pattern": r"approveSync",
        },
        {
            "name": "source_provides_dex_liquidity",
            "pattern": r"placeSync|provideLiquidity|addLiquidity",
        },
        {
            "name": "source_executes_dex_swap",
            "pattern": r"sellSync|buySync|swapSync",
        },
        {
            "name": "source_reads_swap_token_env",
            "pattern": (
                r"TEMPO_SWAP_TOKEN_IN[\s\S]*TEMPO_SWAP_TOKEN_OUT|"
                r"TEMPO_SWAP_TOKEN_OUT[\s\S]*TEMPO_SWAP_TOKEN_IN"
            ),
        },
    ]
)
rk.tempo_onchain_verifier()

rk.tempo_mcp_tool_used("tempo")
