import rewardkit as rk
from tempo_bench_rewardkit.common.checks import (
    register_source_patterns,
    register_tempo_eval_contract,
)

register_tempo_eval_contract()
rk.tempo_rejects_other_blockchains()
rk.tempo_uses_viem_tempo_actions(
    ["token.transferSync"],
    require_faucet_fund_sync=True,
)
register_source_patterns(
    [
        {
            "name": "source_uses_transfer_with_memo_semantics",
            "pattern": r"Actions\.token\.transferSync",
        },
        {
            "name": "source_reads_tempo_memo",
            "pattern": r"TEMPO_MEMO",
        },
        {
            "name": "source_parses_token_units",
            "pattern": r"parseUnits",
        },
        {
            "name": "source_reads_fee_payer_private_key",
            "pattern": r"TEMPO_FEE_PAYER_PRIVATE_KEY",
        },
        {
            "name": "source_passes_fee_payer",
            "pattern": r"feePayer",
        },
        {
            "name": "source_funds_fee_payer",
            "pattern": (
                r"Actions\.faucet\.fundSync[\s\S]*feePayer|"
                r"feePayer[\s\S]*Actions\.faucet\.fundSync"
            ),
        },
        {
            "name": "source_reads_fee_token",
            "pattern": r"TEMPO_FEE_TOKEN",
        },
    ]
)
rk.tempo_onchain_verifier()
