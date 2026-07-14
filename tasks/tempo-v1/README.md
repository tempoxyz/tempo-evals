# Tempo Testnet Integration Suite

Dataset: `tempo/tempo-bench-v1`

## Overview

This suite evaluates whether an agent can build a minimal TypeScript integration
that performs a variety of operations on the Tempo blockchain.

## What It Measures

- Using `viem/tempo` to create, fund, configure, transfer, or
  swap TIP-20 stablecoins.
- Reading task-specific configuration from the environment and producing the
  required output artifact.
- Submitting valid transactions whose onchain effects match the task contract.
- Working effectively with pinned documentation, with or without the Tempo MCP
  server.

Current tasks cover access-key authorization, batched, memo, and
receive-policy-held transfers, fee payment, stablecoin and transfer-policy
creation, faucet funding, fee-token configuration, and Stablecoin DEX swaps.

## Harness

Each task is authored as a Harbor task. Every file is
task-owned and edited in place:

```text
tasks/tempo-v1/<task>/
├── instruction.md           # Agent-facing prompt and output contract
├── task.toml                # Metadata, resources, artifacts, verifier config
├── environment/Dockerfile   # Extends the shared base image
├── solution/                # Minimal oracle used for benchmark validation
└── tests/
    ├── test.sh              # Verifier entry point
    ├── correctness/         # Task criteria and independent onchain verification
    └── quality/             # RewardKit quality checks and weights
```

The task test script first runs the independent onchain verifier. A scored
onchain failure writes a zero Harbor reward and skips RewardKit. On success,
RewardKit's static correctness criteria run first and must all pass or the
complete reward is zero without invoking the quality judge. The published
`correctness` is therefore binary. Passing submissions receive 50% correctness
plus 50% of RewardKit's aggregate `quality` score, which includes the LLM rubric
and trajectory diagnostics. Missing quality configuration or a RewardKit
execution/configuration error produces no reward.

The benchmark job injects access rather than changing task source:

- `docs` serves the revision pinned in `config/tempo-docs.lock.json`.
- `mcp` serves the same pinned revision and also adds the Tempo API MCP server.

Use `--profile all` to launch paired Docs and MCP jobs. Use `--profile docs` or
`--profile mcp` when only one access profile is needed; each profile remains an
independent Harbor job that can be retried and published separately.

## Running the Suite

`bench:matrix:dev` reads `config/models.dev.yaml` and runs Haiku 4.5 once over
every matching task. `bench:matrix:production` reads
`config/models.production.yaml` and runs Haiku 4.5, Sonnet 5, GPT-5.4 mini, and
GPT-5.4 three times per task. Both commands run the full Tempo suite unless
`--task-filter` is provided. `--concurrency` applies independently to each
profile job. Because `--profile all` runs the two profile jobs in parallel,
`--concurrency 32` allows up to 32 trials in each job, or 64 across the pair.
The model configs use a per-provider, per-profile agent concurrency cap of 16.

```bash
# Clean local oracle validation for the suite.
npm run bench:local:oracle -- --task-suite tempo

# Fast local iteration; filter to the task being edited.
npm run bench:local:one -- --task-filter tempo-v1/transfer-with-memo

# Agent smoke run with the MCP profile.
npm run bench:local:agent:dev -- --task-suite tempo --profile mcp \
  --task-filter transfer-with-memo

BASE_IMAGE="$(npm run -s base-image:ref)"

# Haiku over every Tempo task with both access profiles.
npm run bench:matrix:dev -- --task-suite tempo --profile all \
  --base-image "$BASE_IMAGE"

# One-task Haiku smoke with pinned Docs only.
npm run bench:matrix:dev -- --task-suite tempo --profile docs \
  --task-filter transfer-with-memo --base-image "$BASE_IMAGE"

# One-task Haiku smoke with pinned Docs plus Tempo MCP.
npm run bench:matrix:dev -- --task-suite tempo --profile mcp \
  --task-filter transfer-with-memo --base-image "$BASE_IMAGE"

# Full four-model, three-attempt production suite with both profiles.
npm run bench:matrix:production -- --task-suite tempo --profile all \
  --base-image "$BASE_IMAGE"

# Refresh this suite's manifest after task changes.
npm run dataset
```

Use `npm run bench:local:oracle -- --task-suite all` before a cross-suite
change is ready for review. Daytona runs require a CI-published base image via
`--base-image`; see the root README for global environment setup.

## Implementation Notes

Edit task directories directly. `npm run sync` does not rewrite Tempo task
files; it only refreshes shared MPP assets and generated job configurations.

The shared Tempo verifier is installed in the base image and selects the case
named by `TEMPO_BENCH_CASE`. Keep task-specific correctness criteria and onchain
checks in the task directory. Refresh `dataset.toml` after a task change; the
manifest is a required checked-in artifact.
