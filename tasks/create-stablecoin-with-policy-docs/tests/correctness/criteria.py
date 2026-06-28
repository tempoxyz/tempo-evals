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
file_contains_regex("src/index.ts", r"token\.createSync|createSync\(client,\s*\{[\s\S]*currency", name="source_creates_stablecoin")
file_contains_regex("src/index.ts", r"policy\.createSync", name="source_creates_transfer_policy")
file_contains_regex("src/index.ts", r"changeTransferPolicySync|transferPolicy", name="source_links_transfer_policy")
file_contains_regex("src/index.ts", r"TEMPO_STABLECOIN_CURRENCY", name="source_reads_stablecoin_currency")
file_contains_regex("src/index.ts", r"TEMPO_POLICY_ACCOUNT", name="source_reads_policy_account")

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
