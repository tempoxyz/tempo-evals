# MPP Integration Suite

Dataset: `tempo/mpp-bench-v1`

## Overview

This suite evaluates whether an agent can build working MPP clients and services
that use Tempo testnet payments. It covers paid HTTP routes, paid MCP tools,
sessions, custom methods, OpenAPI discovery metadata, and x402 interoperability.

## What It Measures

- Building TypeScript servers and clients around MPP payment flows.
- Correctly processing payments over a wide variety of
  - Payment methods
  - Currencies
  - Progrmaming languages / SDKs

## Harness

MPP tasks use separate agent and verifier environments with a common test
harness. Harbor transfers the declared submission artifacts into the verifier,
which builds or starts the submission, exercises the task-specific scenario,
and records programmatic correctness before RewardKit collects available
quality signals. Server cleanup and verifier logs are handled by the shared
test script.

Each task owns its prompt, metadata, oracle source, task-specific scenario, and
correctness criteria. Files marked `synced` below are copied from `shared/mpp/`
by `npm run sync` and provide the repeatable TypeScript project and test
plumbing:

```text
tasks/mpp/<task>/
├── instruction.md           # Agent-facing prompt (task-owned)
├── task.toml                # Metadata, resources, verifier config (task-owned)
├── environment/Dockerfile   # Agent runtime (generated)
├── solution/
│   ├── src/index.ts         # Minimal oracle implementation (task-owned)
│   └── ...                  # TypeScript project scaffolding (synced)
└── tests/
    ├── Dockerfile           # Separate verifier runtime (generated)
    ├── test.sh              # Harness entry point (synced)
    ├── support/             # Task-specific scenario clients (task-owned)
    ├── correctness/
    │   ├── criteria.py      # Task-specific correctness criteria (task-owned)
    │   └── verify.sh        # Correctness runner (synced)
    └── quality/             # RewardKit quality checks and weights (synced)
```

## Running the Suite

```bash
# Clean local oracle validation for MPP tasks.
npm run bench:local:oracle -- --task-suite mpp

# Fast iteration on one server task.
npm run bench:local:mpp -- --task-filter server-charge-pathusd

# Run a model directly against the MPP task path.
npm run bench:model -- --tasks tasks/mpp \
  --task-filter tempo/mpp-server-charge-pathusd

# Refresh this suite's manifest after task changes.
npm run dataset -- --tasks tasks/mpp
```

### Local mpp.dev docs proxy

Existing MPP tasks can be run against a local mpp.dev checkout without changing
task prompts or verifier contracts. Build the docs checkout first, then pass it
to the model runner:

```bash
cd ~/stripe/mpp
pnpm build

cd ~/stripe/tempo-evals
npm run bench:model -- --tasks tasks/mpp \
  --task-filter server-mcp-pathusd \
  --mpp-docs-source ~/stripe/mpp
```

The runner stages the checkout's built `dist/public` output behind an HTTPS
`mpp.dev` sidecar in each task environment and collects
`/var/log/mpp-docs/access.log` as a job artifact.

Use `npm run bench:local:oracle -- --task-suite all` for clean validation when
a shared change affects multiple suites.

## Implementation Notes

Do not hand-edit files marked `synced` or `generated` above. `npm run sync`
copies the shared harness from `shared/mpp/` and writes both Dockerfiles from
the image configuration. Make shared changes at their source, run
`npm run sync`, and then refresh this suite's dataset manifest.

Task-specific files remain in each task directory, including `task.toml`,
`instruction.md`, oracle sources, scenario clients under `tests/support/`,
task-specific TypeScript verifier probes, and correctness criteria.

A task can intentionally diverge from a shared file only when it is listed in
`mpp.task_local_overrides` in `config/tasks.yaml`.
