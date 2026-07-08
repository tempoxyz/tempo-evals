# Tempo Bench

A evaluation harness for verifying the ability of coding agents to build real Tempo and MPP apps.

Powered by [Harbor](https://harborframework.com)

## Install

```bash
npm install
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

Run a local agent smoke test:

```bash
npm run bench:local:agent:dev
```

Run one task on Daytona:

```bash
npm run bench:daytona:agent:dev -- --task-filter transfer-with-memo-mcp --concurrency 1 --agent-concurrency 1
```

Run the MPP MVP task:

```bash
npm run bench:model -- --tasks tasks/mpp --task-filter tempo/mpp-server-charge-pathusd
```

## Running Development Benchmarks

Development flows are for iteration and smoke testing. They keep attempts low and
are intended to be filtered to one or a few tasks while changing task assets,
verifiers, or agent setup.

Local smoke run:

```bash
npm run bench:local:agent:dev -- --task-filter transfer-with-memo-mcp
```

Daytona smoke run:

```bash
npm run bench:daytona:agent:dev -- --task-filter transfer-with-memo-mcp --concurrency 1 --agent-concurrency 1
```

Useful development options:

| Option | Description |
| ------ | ----------- |
| `--task-filter GLOB` | Run only matching task names, e.g. `transfer-with-memo-mcp` |
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
| `tempo/tempo-bench-v1` | `tasks/tempo/` | Tempo localnet integration tasks across base, docs, and MCP profiles |
| `tempo/mpp-bench-v1` | `tasks/mpp/` | MPP benchmark MVP |

## Profiles

* **Base**: prompt-only Tempo task, no docs sidecar or MCP server.
* **Docs**: local docs sidecar at `TEMPO_DOCS_URL=http://tempo-docs:3000/developers`.
* **MCP**: Harbor MCP config for `tempo` at `https://mcp.tempo.xyz`.

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
| `npm run bench:local:oracle` | Docker | Validate oracle solutions locally |
| `npm run bench:local:agent:dev` | Docker | Local agent smoke run |
| `npm run bench:local:agent` | Docker | Full local agent run |
| `npm run bench:daytona:oracle` | Daytona | Validate oracle solutions remotely |
| `npm run bench:daytona:agent:dev` | Daytona | Remote agent smoke run |
| `npm run bench:daytona:agent` | Daytona | Full remote agent run |
| `npm run bench:production` | Daytona | Production multi-model matrix run |
| `npm run bench:model` | Docker | Ad hoc local model run |

## Environment

| Variable | Used for |
| -------- | -------- |
| `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` | Claude Code and RewardKit LLM judging |
| `OPENAI_API_KEY` | Codex production agent auth |
| `CODEX_AUTH_JSON_PATH` or `CODEX_FORCE_AUTH_JSON` | Optional Codex auth.json auth instead of `OPENAI_API_KEY` |
| `OPENAI_BASE_URL` | Optional Codex OpenAI-compatible endpoint override |
| `DAYTONA_API_KEY` | Daytona runs |
| `DAYTONA_TARGET` | Optional Daytona target |

## References

* [Harbor](https://www.harborframework.com/docs/core-concepts)
* [Tempo docs](https://docs.tempo.xyz/)
* [Tempo MCP](https://mcp.tempo.xyz)
* [MPP](https://mpp.dev/)
