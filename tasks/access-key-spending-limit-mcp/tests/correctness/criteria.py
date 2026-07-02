import rewardkit as rk
import tempo_bench_rewardkit

rk.tempo_typescript_project()
rk.tempo_source_patterns(
    [
        {
            "name": "source_authorizes_access_key",
            "pattern": r"accessKey\.authorizeSync|accessKey\.authorize",
        },
        {
            "name": "source_constructs_access_key_account",
            "pattern": r"Account\.from(?:Secp256k1|P256|HeadlessWebAuthn)[\s\S]*access",
        },
        {
            "name": "source_sets_spending_limits",
            "pattern": r"limits\s*:",
        },
        {
            "name": "source_reads_access_key_limit",
            "pattern": r"TEMPO_ACCESS_KEY_LIMIT",
        },
        {
            "name": "source_uses_access_key_for_transfer",
            "pattern": r"createClient\([\s\S]*accessKey|account:\s*accessKey",
        },
    ]
)
rk.tempo_onchain_verifier()

rk.tempo_trajectory_matches(
    r"tempo|mcp|docs|documentation|search",
)
