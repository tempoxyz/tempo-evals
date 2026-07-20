import rewardkit as rk
from stable_bench_rewardkit.common.checks import (
    register_source_patterns,
    register_tempo_eval_contract,
)

register_tempo_eval_contract()
rk.tempo_rejects_other_blockchains()
rk.tempo_uses_viem_tempo()
register_source_patterns(
    [
        {
            "name": "source_reads_swap_token_env",
            "pattern": (
                r"TEMPO_SWAP_TOKEN_IN[\s\S]*TEMPO_SWAP_TOKEN_OUT|"
                r"TEMPO_SWAP_TOKEN_OUT[\s\S]*TEMPO_SWAP_TOKEN_IN"
            ),
        },
    ]
)
