# Tempo Bench

Harbor benchmark workspace for Tempo and MPP agent evals.

## Vision

Tempo Bench measures whether agents can build working payment integrations, not
just produce plausible code. Each task should provide a clear instruction,
reproducible environment, independent verifier, oracle solution, and gradable harbor rewards.

## Core Abstractions

1. **Dataset** — Harbor task collection.
2. **Task** — `task.toml`, `instruction.md`, `environment/`, `tests/`, and
   `solution/`.
3. **Profile** — Access mode for Tempo tasks: base, docs, or MCP.
4. **Verifier** — Programmatic build/run/onchain/payment check. Writes binary
   Harbor reward.
5. **RewardKit checks** — Diagnostic correctness/quality dimensions. Do not
   treat LLM quality as the primary reward.
6. **Oracle solution** — Minimal reference app copied into `/app`.

## Commands

```bash
npm run docs:prepare        # Build pinned Tempo docs bundle
npm run sync                # Sync generated Tempo variants and shared assets
npm run dataset             # Sync Tempo assets and refresh digests
npm run check               # Compile scripts, run tests, format check, lint
npm run check:scripts       # Python script compile check
npm run check:dataset       # Verify Tempo dataset digest freshness
npm run check:generated     # Verify generated Tempo output freshness
npm run clean               # Remove job/cache output
```

## Jobs

```bash
npm run bench:local:oracle       # Local Docker oracle validation
npm run bench:local:oracle:dev   # Fast local Docker oracle iteration
npm run bench:local:one          # Fast single-concurrency local oracle iteration
npm run bench:local:agent:dev    # Local Docker agent smoke
npm run bench:local:agent        # Full local Docker agent run
npm run bench:daytona:oracle     # Daytona oracle validation
npm run bench:daytona:agent:dev  # Daytona agent smoke
npm run bench:daytona:agent      # Full Daytona agent run
```

Single task:

```bash
npm run bench:local:one -- --task-filter tempo/transfer-with-memo-base
npm run bench:daytona:agent:dev -- --task-filter transfer-with-memo-mcp --concurrency 1 --agent-concurrency 1
```

Use `npm run sync` after changing shared/generated task assets. Use
`npm run bench:local:oracle` for clean local oracle validation before PRs.

MPP MVP:

```bash
npm run bench:model -- --tasks tasks/mpp --task-filter tempo/mpp-server-charge-pathusd
```

## Environment

- `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` for Claude/RewardKit.
- `DAYTONA_API_KEY` for Daytona, or `DAYTONA_JWT_TOKEN` plus
  `DAYTONA_ORGANIZATION_ID`.
- `DAYTONA_TARGET` for optional Daytona target selection.

Never commit `.env`, secrets, key material, logs containing credentials, job
output, or cache output.

## Generated Files

Generated profile task directories in `tasks/tempo/` are generated output; do
not hand-edit them. Authored Tempo task templates live in
`tasks/tempo/_templates/<slug>/` (see `tasks/tempo/_templates/README.md`).
Each template generates `-base`, `-docs`, and `-mcp` variants via
`npm run sync`.

Do not hand-edit the MPP harness files synced from `shared/mpp/` into every
`tasks/mpp/<task>/`:

- `environment/Dockerfile`
- `environment/rewardkit-package/` (from `shared/global/rewardkit-package/`)
- `solution/package.json`
- `solution/solve.sh`
- `solution/tsconfig.json`
- `tests/reward.toml`
- `tests/test.sh`
- `tests/correctness/verify.sh`
- `tests/quality/check.py`
- `tests/quality/reward.toml`
- `tests/support/client_lib.py`
- `tests/support/oracle_paid_server.ts`
- `tests/support/verifier_utils.py`

Task-specific MPP files stay in the task directory: `task.toml`,
`instruction.md`, `solution/` sources, `tests/support/client.py` (scenario),
task-specific `tests/support/*.ts` verifier probes,
`tests/correctness/criteria.py`, and `tests/quality/reward.toml`.
A task can keep a divergent copy of a synced file by listing it under
`mpp.task_local_overrides` in `config/tasks.yaml`; sync then leaves the
task-local copy alone.
When MPP verifier helpers need Node-side logic, write checked-in TypeScript
`.ts` files and run them with `tsx`; do not add `.mjs` verifier helpers or
large inline JavaScript strings in Python.

Task matrix data (task slugs, generated docs/MCP profiles, MPP shared
file lists) lives in `config/tasks.yaml`; `scripts/sync_shared.py` only
executes it.

Harbor job configs are compiled artifacts: `npm run sync` renders
`config/job.yaml.j2` with per-variant values from `config/variants.yaml`,
injects the dataset matrix from
`config/datasets.yaml` unless the variant declares its own `datasets`, and
writes the results to `config/generated/job.<variant>.yaml`. Runs use those
checked-in files; do not hand-edit them. Production runs render the same
template at run time because they depend on the run ID and
`config/models.production.yaml`.

Change the task source or generator, then run:

```bash
npm run sync

# if you want to sync Tempo tasks
npm run dataset

# if you want to sync mpp tasks
npm run dataset -- --tasks tasks/mpp
```

## Eval structure

When writing evals, you SHOULD follow the below principles:

- Keep instructions.md as simple as possible - targeting what a human end-user would prompt. Limit heavy handed scaffolding.
- Write results to log files or static output whenever possible - this makes it easy to write verifiers.
- Use RewardKit whenever possible to write verifiers.
- Do not change weights of graders without explicit prompt -- in most cases the default is fine.
- Write only the minimal set of graders/verifiers to ensure your implementation is accurate. Too many graders are hard to maintain and dilute signal.

### Task README structure

Each task directory should include a concise `README.md` for Harbor Hub display.
Use this structure:

```md
# <Task Title>

## Overview

<One short paragraph describing what the agent must build.>

## What the Task Tests

- <Capability or integration being tested>
- <Capability or integration being tested>

## Verification

- General file structure: <files, scripts, and source layout checked>
- Usage of proper <domain> libraries: <library/API usage checked>
- Correctness of the script, including:
  - <task-specific behavior checked>
  - <task-specific behavior checked>
  - <observable evidence required for success>
```

For Tempo tasks, the README should follow the Harbor Hub pattern above:
overview, capabilities tested, and verification evidence. Keep the verification
section as direct bullet points covering general file structure, proper Tempo
library/API usage, and script correctness. Pull the correctness bullets from the
task's RewardKit criteria and onchain verifier behavior. It can name high-level
verifier checks or onchain events, but should not include exact log paths,
internal score schemas, environment variable tables, or difficulty sections.

For MPP tasks, the README should summarize user-facing server behavior, payment
method/currency expectations, and Tempo testnet behavior. Do not include
implementation details such as environment variable names, `/app/out.json`
schema, exact npm scripts, verifier internals, environment details,
verification, or difficulty sections. Do not add extra requirements not present in
`instruction.md` or `tests/`.

## Coding Style

### General guidelines

- Write simple and ergonomic code
- Leverage harbor built-in methods and functionality whenever possible
- Do not over-abstract, be ok with a small amount of duplication if needed
- Always lint and check your code after any substantial change

### Versioning

This repo is private benchmark infrastructure. Use conventional commits for any
commit:

```text
feat:
fix:
test:
docs:
chore:
refactor:
ci:
perf:
```

Prefer specific messages, e.g. `docs: scaffold benchmark runbook`.

## Pull Requests

### Before opening or updating a PR

If your changes affect generated task assets, shared verifier packages, task
fixtures, or task digests, run the matching artifact sync before committing and
include the resulting generated files in the PR:

```bash
npm run dataset                  # Tempo tasks
npm run dataset -- --tasks tasks/mpp
```

Always sync the relevant dataset manifests before opening or updating a PR.
Do not restore or omit generated dataset/artifact changes just because they look
mechanical. CI expects generated artifacts and dataset digests to be fresh.

### Pull request body

Pull requests should all follow the same format:

```md
## Motivation

<short context>

## Summary

- <change>

## Key design considerations

- <tradeoff or notable detail>
```

Do not include testing summaries in PR descriptions unless notable.
