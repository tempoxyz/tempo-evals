import os

from rewardkit import command_succeeds, file_contains_regex, file_exists


file_exists("package.json", name="package_json_exists")
file_exists("tsconfig.json", name="tsconfig_json_exists")
file_exists("src/index.ts", name="src_index_ts_exists")
file_contains_regex("package.json", r'"build"\s*:', name="package_has_build_script")
file_contains_regex("package.json", r'"run"\s*:', name="package_has_run_script")
file_contains_regex("package.json", r'"viem"\s*:', name="package_depends_on_viem")
file_contains_regex("src/index.ts", r"process\.env", name="source_uses_environment_variables")
file_contains_regex("src/index.ts", r"\b(Address|Hex)\b", name="source_uses_address_or_hex_types")
file_contains_regex("src/index.ts", r"TEMPO_ACCESS_KEY_PRIVATE_KEY", name="source_reads_access_key_private_key")
file_contains_regex("src/index.ts", r"Account\.from(Secp256k1|P256)|fromSecp256k1|fromP256", name="source_creates_access_key_account")
file_contains_regex("src/index.ts", r"accessKey\.authorizeSync|authorizeSync", name="source_authorizes_access_key")
file_contains_regex("src/index.ts", r"TEMPO_ACCESS_KEY_LIMIT", name="source_reads_access_key_limit")
file_contains_regex("src/index.ts", r"account:\s*accessKey", name="source_transfers_with_access_key")
file_contains_regex("src/index.ts", r"transferSync|transferWithMemo", name="source_sends_memo_transfer")
file_contains_regex("src/index.ts", r"TEMPO_MEMO", name="source_reads_tempo_memo")
file_contains_regex("src/index.ts", r"parseUnits", name="source_parses_token_units")

command_succeeds(
    "bash /tests/correctness/verify-tempo.sh",
    timeout=int(os.environ.get("TEMPO_BENCH_REWARDKIT_TIMEOUT_SECONDS", "900")),
    name="tempo_submission_builds_runs_and_emits_onchain_evidence",
)

command_succeeds(
    "test ! -f /logs/trajectory.json || "
    "(grep -Eiq 'docs\\.tempo\\.xyz|TEMPO_DOCS_URL|Tempo docs|documentation' /logs/trajectory.json)",
    timeout=5,
    name="trajectory_uses_tempo_docs_when_available",
)
