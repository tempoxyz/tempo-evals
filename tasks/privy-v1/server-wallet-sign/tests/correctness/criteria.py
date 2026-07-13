import rewardkit as rk
from tempo_bench_rewardkit.common.checks import (
    register_source_patterns,
    register_tempo_eval_contract,
)

register_tempo_eval_contract()
rk.tempo_rejects_other_blockchains()
register_source_patterns(
    [
        {
            "name": "source_uses_privy_node_sdk",
            "pattern": r"@privy-io/node",
        },
        {
            "name": "source_reads_privy_message",
            "pattern": r"PRIVY_MESSAGE",
        },
    ]
)
