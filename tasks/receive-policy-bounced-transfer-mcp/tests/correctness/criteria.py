import rewardkit as rk
import tempo_bench_rewardkit

rk.tempo_typescript_project()
rk.tempo_source_patterns(
    [
        {
            "name": "source_sets_receive_policy",
            "pattern": r"receivePolicy\.setSync|receivePolicy\.set",
        },
        {
            "name": "source_reads_recipient_private_key",
            "pattern": r"TEMPO_RECIPIENT_PRIVATE_KEY",
        },
        {
            "name": "source_reads_policy_ids",
            "pattern": (
                r"TEMPO_RECEIVE_POLICY_SENDER_POLICY_ID[\s\S]*TEMPO_RECEIVE_POLICY_TOKEN_POLICY_ID|"
                r"TEMPO_RECEIVE_POLICY_TOKEN_POLICY_ID[\s\S]*TEMPO_RECEIVE_POLICY_SENDER_POLICY_ID"
            ),
        },
        {
            "name": "source_sends_transfer_after_policy",
            "pattern": r"transferSync|transferWithMemo",
        },
    ]
)
rk.tempo_onchain_verifier()

rk.tempo_trajectory_matches(
    r"tempo|mcp|docs|documentation|search",
)
