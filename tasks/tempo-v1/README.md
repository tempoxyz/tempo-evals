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
- Working effectively with either pinned documentation or the Tempo MCP server.

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

The task test script first runs the independent onchain verifier. A failed
onchain check writes a zero Harbor reward and skips RewardKit. On success,
RewardKit aggregates the available static and LLM quality criteria into the
primary reward.

The benchmark job injects access rather than changing task source:

- `docs` serves the revision pinned in `config/tempo-docs.lock.json`.
- `mcp` adds the Tempo API MCP server.
- `--profile all` runs paired Docs and MCP jobs over the same task artifact.

## Running the Suite

```bash
# Clean local oracle validation for the suite.
npm run bench:local:oracle -- --task-suite tempo

# Fast local iteration; filter to the task being edited.
npm run bench:local:one -- --task-filter tempo-v1/transfer-with-memo

# Agent smoke run with the MCP profile.
npm run bench:local:agent:dev -- --task-suite tempo --profile mcp \
  --task-filter transfer-with-memo

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
named by `TEMPO_BENCH_CASE`. Keep task-specific correctness criteria and
onchain checks in the task directory. Refresh `dataset.toml` after a task
change; the manifest is a required checked-in artifact.
