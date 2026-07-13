from tempo_bench_rewardkit.common.checks import (
    register_source_patterns,
    register_tempo_eval_contract,
)

register_tempo_eval_contract()
register_source_patterns(
    [
        {
            "name": "source_uses_privy_node_sdk",
            "pattern": r"@privy-io/node",
        },
        {
            "name": "source_reads_allowed_recipient",
            "pattern": r"PRIVY_ALLOWED_RECIPIENT",
        },
    ]
)
