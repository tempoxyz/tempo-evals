import rewardkit as rk
from tempo_bench_rewardkit.common.checks import (
    register_source_patterns,
    register_tempo_eval_contract,
)

register_tempo_eval_contract()
rk.tempo_rejects_other_blockchains()
rk.tempo_uses_viem_tempo_actions(["faucet.fund", "token.transfer"])
register_source_patterns(
    [
        {
            "name": "source_reads_faucet_private_key",
            "pattern": r"TEMPO_FAUCET_PRIVATE_KEY",
        },
    ]
)
