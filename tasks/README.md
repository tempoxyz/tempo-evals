# tempo/tempo-bench

Local Harbor dataset for Tempo integration evaluations.

Current tasks:

- `tempo/transfer-with-memo`
- `tempo/transfer-with-memo-docs-mcp`
- `tempo/transfer-with-memo-fee-payer`
- `tempo/set-fee-token`
- `tempo/create-stablecoin-with-policy`
- `tempo/faucet-funded-transfer`
- `tempo/stablecoin-dex-swap`

Each task should stay Harbor-native and self-contained:

- `instruction.md` contains only the agent-facing prompt.
- `task.toml` owns fixture values, verifier selection, resources, and sidecars.
  Put agent-facing fixture values in `[environment.env]` and grader-facing
  fixture values in `[verifier.env]`; the sync script checks Tempo keys match.
- `environment/` contains the task runtime and Docker Compose additions. Common
  sidecars are symlinked from `../shared/` where Harbor and Docker can consume
  them.
- `tests/criteria/check.py` contains the task's explicit built-in RewardKit
  file/regex/docs criteria. `tests/e2e/check.py` contains the e2e command
  criterion. `tests/reward.toml` is task-local and aggregates the criteria and
  e2e dimensions with `threshold = 1.0`. `tests/test.sh` is the verifier
  entrypoint, and `tests/tempo-bench-verifier/` is a minimal copied verifier
  package for the selected `TEMPO_BENCH_CASE`.
- `solution/` contains the oracle solution used for sanity checks. It is a
  normal minimal TypeScript app; `solve.sh` only copies the files into `/app`.

Edit shared verifier or localnet code under `../shared/`, then run
`make sync` from the repository root before running Harbor or refreshing
`dataset.toml`.
