# tempo/tempo-bench-v1

Local Harbor dataset for Tempo integration evaluations.

Current task intents:

- `tempo/transfer-with-memo`
- `tempo/transfer-with-memo-fee-payer`
- `tempo/set-fee-token`
- `tempo/create-stablecoin-with-policy`
- `tempo/faucet-funded-transfer`
- `tempo/stablecoin-dex-swap`

Each intent is materialized into `-docs` and `-mcp` profile variants
by `npm run sync`.

Each task should stay Harbor-native and self-contained:

- `instruction.md` contains only the agent-facing prompt.
- `task.toml` owns fixture values, verifier selection, resources, and sidecars.
  Put Tempo fixture values in `[environment.env]`; shared compose injects those
  keys into `main` so shared-mode verifier commands inherit the same env. The
  sync script rejects duplicated `[verifier.env]` blocks.
- `environment/` contains the task runtime and Docker Compose additions. Common
  sidecars are symlinked from `../../shared/` where Harbor and Docker can consume
  them.
- `tests/correctness/` contains the task's explicit built-in RewardKit
  file/regex/docs criteria plus the e2e command criterion.
  `tests/quality/` contains non-binary turn/token efficiency checks and the
  Claude Haiku LLM judge. `tests/test.sh` writes Harbor's primary
  `/logs/verifier/reward.json` as a single binary `reward` key from the
  independent Tempo verifier's build/run/onchain result; RewardKit correctness
  and quality dimensions are diagnostic. `tests/tempo-bench-verifier/` is a
  minimal copied verifier package for the selected `TEMPO_BENCH_CASE`.
- `solution/` contains the oracle solution used for sanity checks. It is a
  normal minimal TypeScript app; `solve.sh` only copies the files into `/app`.

Edit shared verifier or localnet code under `../../shared/`, then run
`npm run sync` from the repository root before running Harbor or refreshing
`dataset.toml`.
