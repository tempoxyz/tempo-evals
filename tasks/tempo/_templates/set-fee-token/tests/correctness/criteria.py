import rewardkit as rk
from tempo_bench_rewardkit.common.checks import (
    register_source_patterns,
    register_tempo_typescript_project,
)

register_tempo_typescript_project()
register_source_patterns(
    [
        {
            "name": "source_calls_set_user_token",
            "pattern": r"setUserToken",
        },
        {
            "name": "source_reads_tempo_fee_token",
            "pattern": r"TEMPO_FEE_TOKEN",
        },
    ]
)
rk.tempo_onchain_verifier()
