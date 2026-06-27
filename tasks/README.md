# tempo/tempo-bench

Local Harbor dataset for Tempo integration evaluations.

Current tasks:

- `tempo/transfer-with-memo`
- `tempo/transfer-with-memo-docs-mcp`

Each task should stay Harbor-native and self-contained:

- `instruction.md` contains only the agent-facing prompt.
- `task.toml` owns fixture values, verifier selection, resources, and sidecars.
  Put agent-facing fixture values in `[environment.env]` and grader-facing
  fixture values in `[verifier.env]`; the sync script checks Tempo keys match.
- `environment/` contains the task runtime and Docker Compose additions.
- `tests/` contains the verifier entrypoint and vendored shared verifier package.
- `solution/` contains the oracle solution used for sanity checks.

Edit shared verifier or localnet code under `../shared/`, then run
`node ../scripts/sync-shared.mjs` from the repository root before running Harbor
or refreshing `dataset.toml`.
