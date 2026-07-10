# tempo/tempo-bench-v1

Harbor dataset for Tempo integration evaluations on Tempo testnet.

Task directories in this directory are the authored Tempo benchmark tasks.
Edit them directly. `npm run sync` refreshes dataset manifests, MPP shared
harness files, and generated job configurations; it does not rewrite Tempo
task files.

Current task intents:

- `tempo-v1/transfer-batched`
- `tempo-v1/transfer-with-memo`
- `tempo-v1/transfer-with-memo-fee-payer`
- `tempo-v1/set-fee-token`
- `tempo-v1/create-stablecoin-with-policy`
- `tempo-v1/faucet-funded-transfer`
- `tempo-v1/stablecoin-dex-swap`

Each task is run with either the Docs or MCP access profile. Docs uses Tempo's
public documentation by default and can serve a pinned bundle with
`--docs-sha`; MCP adds the Tempo MCP server at the job level. Both profiles use
the same task artifact.

Each task is authored directly as a Harbor task:

- `instruction.md` is the agent-facing prompt and output contract.
- `task.toml` owns task metadata, environment defaults, verifier selection,
  and resource limits. Profile configuration is applied by the benchmark job.
- `environment/Dockerfile` extends the shared benchmark base image.
- `tests/correctness/` contains task-specific RewardKit criteria and the
  independent onchain verifier. `tests/quality/` contains turn/token
  efficiency checks and the Claude Haiku LLM judge. `tests/test.sh` runs the
  onchain verifier first: failure writes Harbor's primary
  `/logs/verifier/reward.json` as zero and skips RewardKit. On success,
  RewardKit writes the primary score from the weighted aggregate of all static
  and available LLM quality criteria. A score of one requires every included
  criterion to score one. The shared Tempo verifier is installed in the base
  image and selects the case named by `TEMPO_BENCH_CASE`.
- `solution/` contains the oracle solution used for sanity checks.

After changing a task, run `npm run dataset` to refresh `dataset.toml` digests.
This v1 dataset is an immutable evaluation contract; incompatible changes
belong in a new major benchmark version.
