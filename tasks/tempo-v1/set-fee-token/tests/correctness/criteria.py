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
            "name": "source_reads_tempo_fee_token",
            "pattern": r"TEMPO_FEE_TOKEN",
        },
    ]
)
