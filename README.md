# Tempo Bench

A evaluation harness for verifying the ability of coding agents to build real Tempo and MPP apps.

Powered by [Harbor](https://harborframework.com)

## Install

```bash
uv sync
npm run docs:prepare
```

Optional Harbor install:

```bash
uv tool install 'harbor[daytona]'
```

## Quick Start

Validate the Tempo oracle solutions locally:

```bash
npm run bench:local:oracle
```

Validate both task families explicitly:

```bash
npm run bench:local:oracle -- --task-suite all
```

Fast oracle loop for one task while editing:

```bash
npm run bench:local:one -- --task-filter tempo/transfer-with-memo
```

Fast Tempo oracle loop:

```bash
npm run bench:local:tempo
```

Fast MPP oracle loop:

```bash
npm run bench:local:mpp -- --task-filter server-charge-pathusd
```

Run a local agent smoke test:

```bash
npm run bench:local:agent:dev
```

Run one task on Daytona:

```bash
npm run bench:daytona:agent:dev -- --task-filter transfer-with-memo-mcp --concurrency 1 --agent-concurrency 1
```

Run the MPP task family with the generic runner:

```bash
npm run bench:local:oracle -- --task-suite mpp
```

## Running Development Benchmarks

Development flows are for iteration and smoke testing. They keep attempts low and
are intended to be filtered to one or a few tasks while changing task assets,
verifiers, or agent setup.

Local Tempo smoke run:

```bash
npm run bench:local:agent:dev -- --task-filter transfer-with-memo-mcp
```

Local MPP smoke run:

```bash
npm run bench:local:agent:dev -- --task-suite mpp --task-filter server-charge-pathusd
```

Daytona Tempo smoke run:

```bash
npm run bench:daytona:agent:dev -- --task-filter transfer-with-memo-mcp --concurrency 1 --agent-concurrency 1
```

Daytona MPP smoke run:

```bash
npm run bench:daytona:agent:dev -- --task-suite mpp --task-filter server-charge-pathusd --concurrency 1 --agent-concurrency 1
```

Useful development options:

| Option | Description |
| ------ | ----------- |
| `--task-filter GLOB` | Run only matching task names, e.g. `transfer-with-memo-mcp` |
| `--task-suite SUITE` | Select `tempo`, `mpp`, or `all`; default is `tempo` |
| `--concurrency N` | Override total concurrent trials |
| `--agent-concurrency N` | Override concurrent agent executions |
| `--max-retries N` | Retry transient trial/setup failures |
| `--no-sync` | Skip generated asset and dataset sync before running |

## Running Production Benchmarks

Production runs execute the full Tempo task matrix on Daytona across the configured
agent/model list. Raw Harbor output is written under `runs/<run_id>/harbor-job`, with
run metadata in `runs/<run_id>/metadata.json`.

Configure the model matrix in `config/models.production.yaml`:

```yaml
models:
  - claude-haiku-4-5
  - agent: codex
    model_name: gpt-5
```

Run the production matrix:

```bash
npm run bench:production
```

Run a limited production check:

```bash
npm run bench:production -- --task-filter transfer-with-memo-mcp --concurrency 1 --agent-concurrency 1
```

View raw Harbor results:

```bash
uv run harbor view runs/<run_id>/harbor-job
```

Export CSV and JSON results for notebooks or external tools:

```bash
npm run results:export -- --job runs/<run_id>/harbor-job --run-id <run_id>
```

Production options:

| Option | Description |
| ------ | ----------- |
| `--models-config PATH` | Use a different production model matrix config |
| `--task-filter GLOB` | Run a limited task subset for production validation |
| `--concurrency N` | Override production `n_concurrent_trials` |
| `--agent-concurrency N` | Override per-model `n_concurrent` from the model config |
| `--max-retries N` | Override Daytona retry count, default `2` |
| `--job-name NAME` | Use a custom production run id under `runs/` |

Export outputs are written to `runs/<run_id>/exports/` by default:

| File | Description |
| ---- | ----------- |
| `trials.csv` | One row per Harbor trial result |
| `summary.csv` | Aggregates by model, agent, task, task family, and profile |
| `summary.json` | Structured aggregate data and export metadata |

## Datasets

| Dataset | Path | Description |
| ------- | ---- | ----------- |
| `tempo/tempo-bench-v1` | `tasks/tempo-v1/` | Tempo localnet integration tasks across docs and MCP profiles |
| `tempo/mpp-bench-v1` | `tasks/mpp/` | MPP benchmark MVP |

Benchmark majors are immutable evaluation contracts: task set, prompts,
fixtures, verifier behavior, and scoring rules. Compatible maintenance fixes
are tracked in Git; changes that make results incomparable require a new
versioned dataset (for example, `tempo-bench-v2`). Canonical benchmark IDs and
Harbor dataset names live in `config/benchmarks.yaml`.

## Profiles

* **Docs**: public Tempo documentation by default; `--docs-sha` (or a checked-in default SHA) serves a pinned local docs bundle instead.
* **MCP**: the Docs profile plus Harbor MCP config for `tempo` at `https://mcp.tempo.xyz`.

## CLI

```bash
# Sync generated Tempo task assets
npm run sync

# Refresh Tempo dataset digests
npm run dataset

# Refresh MPP MVP dataset digest
npm run dataset -- --tasks tasks/mpp

# Check scripts, format, and lint
npm run check

# Check generated Tempo files
npm run check:generated

# Open Harbor job viewer
npm run harbor:view

# Clean job/cache output
npm run clean
```

## Jobs

| Command | Runtime | Description |
| ------- | ------- | ----------- |
| `npm run bench:local:oracle` | Docker | Validate Tempo oracle solutions locally |
| `npm run bench:local:oracle:dev` | Docker | Fast Tempo oracle run; skips sync and reuses environment builds |
| `npm run bench:local:tempo` | Docker | Fast Tempo oracle run; skips sync and reuses environment builds |
| `npm run bench:local:mpp` | Docker | Fast MPP oracle run; skips sync and reuses environment builds |
| `npm run bench:local:all` | Docker | Fast all-task oracle run; skips sync and reuses environment builds |
| `npm run bench:local:one` | Docker | Fast one-concurrency local oracle run; pass `--task-filter` |
| `npm run bench:local:agent:dev` | Docker | Local Tempo agent smoke run |
| `npm run bench:local:agent` | Docker | Local Tempo agent run |
| `npm run bench:daytona:oracle` | Daytona | Validate Tempo oracle solutions remotely |
| `npm run bench:daytona:agent:dev` | Daytona | Remote Tempo agent smoke run |
| `npm run bench:daytona:agent` | Daytona | Remote Tempo agent run |
| `npm run bench:production` | Daytona | Production multi-model matrix run |
| `npm run bench:model` | Docker | Ad hoc local model run |

## Dev Loop

Use the dev oracle commands while iterating on one Tempo task:

```bash
npm run bench:local:one -- --task-filter tempo/transfer-with-memo
```

Use `npm run bench:local:mpp` for the same fast loop over MPP tasks. Commands
default to Tempo. Use `--task-suite all` or `npm run bench:local:all` when you
intentionally want both Tempo and MPP tasks.

These commands use `local-oracle-dev`, skip generated asset sync, and avoid
forced Docker rebuilds. Run `npm run sync` after changing shared/generated task
assets. Run
`npm run bench:local:oracle -- --task-suite all` before opening a PR for clean
validation across both task families.

Useful runner flags:

```bash
--no-sync               # skip sync_shared.py and harbor sync
--no-force-build        # ask Harbor to reuse Docker builds
--no-delete             # keep environments for debugging
--disable-verification  # skip verifier execution
--install-only          # run setup/install only
--debug                 # enable Harbor debug logs
```

## Environment

| Variable | Used for |
| -------- | -------- |
| `ANTHROPIC_API_KEY` | Claude Code and RewardKit LLM judging |
| `OPENAI_API_KEY` | Codex production agent auth |
| `DAYTONA_API_KEY` | Daytona runs |
| `DAYTONA_TARGET` | Optional Daytona target |

## References

* [Harbor](https://www.harborframework.com/docs/core-concepts)
* [Tempo docs](https://docs.tempo.xyz/)
* [Tempo MCP](https://mcp.tempo.xyz)
* [MPP](https://mpp.dev/)
