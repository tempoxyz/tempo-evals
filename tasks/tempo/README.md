# tempo/tempo-bench-v1

Local Harbor dataset for Tempo integration evaluations.

Generated task directories in this directory are build artifacts. Do not edit
profile task directories here; edit the authored templates in
`_templates/<slug>/` and the shared assets in `../../shared/`, then run
`npm run sync` from the repository root. See `_templates/README.md` for the
authoring guide.

Current task intents:

- `tempo/transfer-with-memo`
- `tempo/transfer-with-memo-fee-payer`
- `tempo/access-key-transfer`
- `tempo/set-fee-token`
- `tempo/create-stablecoin-with-policy`
- `tempo/faucet-funded-transfer`
- `tempo/stablecoin-dex-swap`

Each intent is materialized into `-base`, `-docs`, and `-mcp` profile
variants by `npm run sync`.

Each generated task is Harbor-native and self-contained:

- `instruction.md` is the agent-facing prompt rendered from the source
  instruction plus the shared execution constraints and profile block.
- `task.toml` owns fixture values, verifier selection, resources, and
  sidecars, rendered from the source `task.toml` plus per-profile env and
  MCP server config.
- `environment/` contains the task runtime and Docker Compose additions.
  Common sidecars are symlinked from `../../shared/` where Harbor and Docker
  can consume them.
- `tests/correctness/` contains the task's RewardKit criteria plus the e2e
  command criterion. `tests/quality/` contains non-binary turn/token
  efficiency checks and the Claude Haiku LLM judge. `tests/test.sh` writes
  Harbor's primary `/logs/verifier/reward.json` as a single binary `reward`
  key from the independent Tempo verifier's build/run/onchain result;
  RewardKit correctness and quality dimensions are diagnostic.
  `tests/tempo-bench-verifier/` is a minimal copied verifier package for the
  selected `TEMPO_BENCH_CASE`.
- `solution/` contains the oracle solution used for sanity checks.

After changing sources or shared code, run `npm run sync`, then
`npm run dataset` to refresh `dataset.toml` digests.
