import rewardkit as rk
from tempo_bench_rewardkit.common.checks import (
    register_source_patterns,
    register_tempo_typescript_project,
)

register_tempo_typescript_project()
rk.tempo_rejects_other_blockchains()
rk.tempo_uses_viem_tempo_actions(
    ["token.transferSync"],
    require_faucet_fund_sync=True,
)
register_source_patterns(
    [
        {
            "name": "source_calls_faucet_fund",
            "pattern": r"Actions\.faucet\.fundSync",
        },
        {
            "name": "source_reads_faucet_private_key",
            "pattern": r"TEMPO_FAUCET_PRIVATE_KEY",
        },
        {
            "name": "source_sends_transfer",
            "pattern": r"Actions\.token\.transferSync",
        },
    ]
)
rk.tempo_onchain_verifier()
