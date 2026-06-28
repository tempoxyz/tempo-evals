from rewardkit import file_contains_regex, file_exists


file_exists("package.json", name="package_json_exists")
file_exists("tsconfig.json", name="tsconfig_json_exists")
file_exists("src/index.ts", name="src_index_ts_exists")
file_contains_regex("package.json", r'"build"\s*:', name="package_has_build_script")
file_contains_regex("package.json", r'"run"\s*:', name="package_has_run_script")
file_contains_regex("package.json", r'"viem"\s*:', name="package_depends_on_viem")
file_contains_regex("src/index.ts", r"process\.env", name="source_uses_environment_variables")
file_contains_regex("src/index.ts", r"\b(Address|Hex)\b", name="source_uses_address_or_hex_types")
file_contains_regex("src/index.ts", r"Actions\.dex|\.dex\.", name="source_uses_dex_actions")
file_contains_regex("src/index.ts", r"approveSync", name="source_approves_dex_spending")
file_contains_regex("src/index.ts", r"placeSync|provideLiquidity|addLiquidity", name="source_provides_dex_liquidity")
file_contains_regex("src/index.ts", r"sellSync|buySync|swapSync", name="source_executes_dex_swap")
file_contains_regex("src/index.ts", r"TEMPO_SWAP_TOKEN_IN[\s\S]*TEMPO_SWAP_TOKEN_OUT|TEMPO_SWAP_TOKEN_OUT[\s\S]*TEMPO_SWAP_TOKEN_IN", name="source_reads_swap_token_env")
