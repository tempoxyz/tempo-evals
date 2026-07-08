import rewardkit as rk
from tempo_bench_rewardkit.common.checks import (
    register_source_patterns,
    register_tempo_typescript_project,
)

register_tempo_typescript_project()
register_source_patterns(
    [
        {
            "name": "source_creates_stablecoin",
            "pattern": r"token\.createSync|createSync\(client,\s*\{[\s\S]*currency",
        },
        {
            "name": "source_creates_transfer_policy",
            "pattern": r"policy\.createSync",
        },
        {
            "name": "source_links_transfer_policy",
            "pattern": r"changeTransferPolicySync|transferPolicy",
        },
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
rk.tempo_onchain_verifier()
