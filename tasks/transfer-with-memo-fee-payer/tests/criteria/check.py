from rewardkit import file_contains_regex, file_exists


file_exists("package.json", name="package_json_exists")
file_exists("tsconfig.json", name="tsconfig_json_exists")
file_exists("src/index.ts", name="src_index_ts_exists")
file_contains_regex("package.json", r'"build"\s*:', name="package_has_build_script")
file_contains_regex("package.json", r'"run"\s*:', name="package_has_run_script")
file_contains_regex("package.json", r'"viem"\s*:', name="package_depends_on_viem")
file_contains_regex("src/index.ts", r"process\.env", name="source_uses_environment_variables")
file_contains_regex("src/index.ts", r"\b(Address|Hex)\b", name="source_uses_address_or_hex_types")
file_contains_regex("src/index.ts", r"transferWithMemo|transferSync", name="source_uses_transfer_with_memo_semantics")
file_contains_regex("src/index.ts", r"TEMPO_MEMO", name="source_reads_tempo_memo")
file_contains_regex("src/index.ts", r"parseUnits", name="source_parses_token_units")
file_contains_regex("src/index.ts", r"TEMPO_FEE_PAYER_PRIVATE_KEY", name="source_reads_fee_payer_private_key")
file_contains_regex("src/index.ts", r"feePayer", name="source_passes_fee_payer")
file_contains_regex("src/index.ts", r"TEMPO_FEE_TOKEN", name="source_reads_fee_token")
