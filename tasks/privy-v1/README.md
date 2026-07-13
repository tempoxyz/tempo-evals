# Privy Server Wallet Integration Suite

Dataset: `tempo/privy-bench-v1`

## Overview

This suite evaluates whether an agent can build a minimal TypeScript
integration against the Privy server-wallet APIs from the public documentation
at https://docs.privy.io, including one task that pays with a Privy wallet on
the Tempo testnet.

## What It Measures

- Using the Privy Node SDK (`@privy-io/node`) to create Ethereum server
  wallets, sign messages and transactions, and govern wallets with policies.
- Reading task-specific configuration from the environment and producing the
  required output artifact.
- Producing evidence the verifier can check independently against the Privy
  API, offline signature recovery, and Tempo onchain state.

Current tasks cover server wallet creation, message signing, a Tempo testnet
stablecoin transfer paid by a Privy wallet, and recipient-allowlist policy
enforcement.

## Harness

Each task is authored as a Harbor task. Every file is task-owned and edited in
place:

```text
tasks/privy-v1/<task>/
├── instruction.md           # Agent-facing prompt and output contract
├── task.toml                # Metadata, resources, artifacts, verifier config
├── environment/Dockerfile   # Extends the shared base image
├── solution/                # Minimal oracle used for benchmark validation
└── tests/
    ├── test.sh              # Verifier entry point
    ├── correctness/         # Task criteria and independent verification
    └── quality/             # RewardKit quality checks and weights
```

The task test script first runs the shared verifier, which executes the
submission with `npm run eval`, reads `/app/out.json`, and checks the reported
evidence against the Privy API (wallet existence, chain type, attached
policies), offline signature recovery, live policy probes, and — for the
send-transaction task — Tempo onchain state. A failed correctness check writes
a zero Harbor reward and skips RewardKit.

## Credentials

Tasks and the verifier require Privy API credentials in the run environment:

- `PRIVY_APP_ID`
- `PRIVY_APP_SECRET`

Set them in `.env` (or the file passed via `--env-file`). The job config
forwards them to the verifier, which supplies them to the submission at
execution time. Use a dedicated Privy app for benchmark runs: tasks create
wallets and policies in the app on every run.

Privy tasks must run in a Privy-only job. Mixed-suite runs intentionally fail
before execution so the Privy credentials are never supplied to unrelated
task submissions.

## Running the Suite

```bash
# Clean local oracle validation for the suite.
npm run bench:local:privy

# Fast local iteration; filter to the task being edited.
npm run bench:local:one -- --task-suite privy --task-filter privy-v1/server-wallet-create

# Agent smoke run.
npm run bench:local:agent:dev -- --task-suite privy
```

## Implementation Notes

- Verifier cases live in `shared/tempo/verifier/src/cases/privy-*.js` and are
  selected per task via `TEMPO_BENCH_CASE`.
- `server-wallet-sign` and `wallet-policy-enforcement` receive per-run values
  (`PRIVY_MESSAGE`, `PRIVY_ALLOWED_RECIPIENT`) from the verifier so reported
  evidence cannot be precomputed.
- Only `server-wallet-send-tx` needs Tempo RPC access; the other cases run
  with `needsChain: false`.
