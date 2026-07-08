import rewardkit as rk
from tempo_bench_rewardkit.common.checks import (
    register_source_patterns,
    register_tempo_typescript_project,
)

register_tempo_typescript_project()
register_source_patterns(
    [
        {
            "name": "source_calls_faucet_fund",
            "pattern": r"tempo_fundAddress|faucet\.fundSync|fundSync",
        },
        {
            "name": "source_reads_faucet_private_key",
            "pattern": r"TEMPO_FAUCET_PRIVATE_KEY",
        },
        {
            "name": "source_sends_transfer",
            "pattern": (
                r"transferSync|transferWithMemo|"
                r"functionName\s*:\s*[\"']transfer[\"']|"
                r"name\s*:\s*[\"']transfer[\"']"
            ),
        },
    ]
)
rk.tempo_onchain_verifier()
