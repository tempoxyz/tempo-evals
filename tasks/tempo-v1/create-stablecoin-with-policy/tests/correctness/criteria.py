import rewardkit as rk
from tempo_bench_rewardkit.common.checks import (
    register_source_patterns,
    register_tempo_eval_contract,
)

register_tempo_eval_contract()
rk.tempo_rejects_other_blockchains()
rk.tempo_uses_viem_tempo()
register_source_patterns(
    [
        {
            "name": "source_reads_stablecoin_currency",
            "pattern": r"TEMPO_STABLECOIN_CURRENCY",
        },
        {
            "name": "source_reads_policy_account",
            "pattern": r"TEMPO_POLICY_ACCOUNT",
        },
    ]
)
