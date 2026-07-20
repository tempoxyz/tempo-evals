# Tempo Testnet Integration Suite

Dataset: `tempo/stable-bench-v1`

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

Each task is authored as a Harbor task. `npm run sync` generates the two leaf
Dockerfiles from the configured agent and verifier images; the remaining files
are task-owned:

```text
tasks/tempo-v1/<task>/
├── instruction.md           # Agent-facing prompt and output contract
├── task.toml                # Metadata, resources, artifacts, verifier config
├── environment/Dockerfile   # Agent runtime (generated)
├── solution/                # Minimal oracle used for benchmark validation
└── tests/
    ├── Dockerfile           # Separate verifier runtime (generated)
    ├── test.sh              # Verifier entry point
    ├── correctness/         # Task criteria and independent onchain verification
    └── quality/             # RewardKit quality checks and weights
```

Harbor transfers the declared submission artifacts into a separate verifier
environment. The task first runs the independent onchain verifier. A scored
onchain failure publishes `correctness = 0`, `quality = 0`, and `reward = 0`,
then skips RewardKit. On success, Harbor receives `correctness = 1`. Published
`quality` is the mean of RewardKit's static code score and its aggregate LLM
and trajectory quality score. Harbor then publishes `reward = quality`, so
functional correctness gates the reward without contributing additional
weight. Missing quality configuration or a RewardKit execution/configuration
error produces no reward.

The benchmark job injects access rather than changing task source. For requests
made from within the task sandbox:

- `docs` serves the revision pinned in `config/tempo-docs.lock.json`.
- `mcp` serves the same pinned revision and also adds the Tempo API MCP server.

OpenAI models are an exception: Codex's hosted web fetch reads the live public
docs outside the sandbox and therefore does not honor the pinned docs SHA. See
[Access Profiles](../../README.md#access-profiles) for details.

Use `--profile all` to launch paired Docs and MCP jobs. Use `--profile docs` or
`--profile mcp` when only one access profile is needed; each profile remains an
independent Harbor job that can be retried and published separately.

## Running the Suite

`bench:matrix:dev` reads `config/models.dev.yaml` and runs Haiku 4.5 once over
every matching task. `bench:matrix:production` reads
`config/models.production.yaml` and runs Fable 5, Opus 4.8, Haiku 4.5,
Sonnet 5, GPT-5.4 mini, GPT-5.6 Sol, GPT-5.6 Terra, and GPT-5.6 Luna three
times per task. Both commands run the full Tempo suite unless
`--task-filter` is provided. `--concurrency` applies independently to each
profile job. Because `--profile all` runs the two profile jobs in parallel, the
production default of 16 allows up to 16 trials in each job, or 32 across the
pair. The production model config uses a per-provider, per-profile agent
concurrency cap of 16.

```bash
# Clean local oracle validation for the suite.
npm run bench:local:oracle -- --task-suite tempo

# Fast local iteration; filter to the task being edited.
npm run bench:local:one -- --task-filter tempo-v1/transfer-with-memo

# Agent smoke run with the MCP profile.
npm run bench:local:agent:dev -- --task-suite tempo --profile mcp \
  --task-filter transfer-with-memo

AGENT_IMAGE="$(npm run -s agent-image:ref)"
VERIFIER_IMAGE="$(npm run -s verifier-image:ref)"

# Haiku over every Tempo task with both access profiles.
npm run bench:matrix:dev -- --task-suite tempo --profile all \
  --agent-image "$AGENT_IMAGE" --verifier-image "$VERIFIER_IMAGE"

# One-task Haiku smoke with pinned Docs only.
npm run bench:matrix:dev -- --task-suite tempo --profile docs \
  --task-filter transfer-with-memo \
  --agent-image "$AGENT_IMAGE" --verifier-image "$VERIFIER_IMAGE"

# One-task Haiku smoke with pinned Docs plus Tempo MCP.
npm run bench:matrix:dev -- --task-suite tempo --profile mcp \
  --task-filter transfer-with-memo \
  --agent-image "$AGENT_IMAGE" --verifier-image "$VERIFIER_IMAGE"

# Full eight-model, three-attempt production suite with both profiles.
npm run bench:matrix:production -- --task-suite tempo --profile all \
  --agent-image "$AGENT_IMAGE" --verifier-image "$VERIFIER_IMAGE"

# Refresh this suite's manifest after task changes.
npm run dataset
```

Use `npm run bench:local:oracle -- --task-suite all` before a cross-suite
change is ready for review. Daytona runs require CI-published agent and verifier
images; see the root README for global environment setup.

## Implementation Notes

Edit task-owned files directly. `npm run sync` refreshes both generated
Dockerfiles. The Tempo verifier is installed only in the verifier image and
selects the case named by `STABLE_BENCH_CASE`. Keep task-specific correctness
criteria and onchain checks in the task directory. Refresh `dataset.toml` after
a task change; the manifest is a required checked-in artifact.
