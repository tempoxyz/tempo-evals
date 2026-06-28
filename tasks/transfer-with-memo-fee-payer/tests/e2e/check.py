import os

from rewardkit import command_succeeds


command_succeeds(
    "bash /tests/e2e/verify-tempo.sh",
    timeout=int(os.environ.get("TEMPO_BENCH_REWARDKIT_TIMEOUT_SECONDS", "900")),
    name="tempo_submission_builds_runs_and_emits_onchain_evidence",
)
