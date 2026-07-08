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

## Datasets

| Dataset | Path | Description |
| ------- | ---- | ----------- |
| `tempo/tempo-bench-v1` | `tasks/` | Tempo localnet integration tasks across base, docs, and MCP profiles |
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
| `npm run bench:model` | Docker | Ad hoc local model run |

## Environment

| Variable | Used for |
| -------- | -------- |
| `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` | Claude Code and RewardKit LLM judging |
| `DAYTONA_API_KEY` | Daytona runs |
| `DAYTONA_TARGET` | Optional Daytona target |

## References

* [Harbor](https://www.harborframework.com/docs/core-concepts)
* [Tempo docs](https://docs.tempo.xyz/)
* [Tempo MCP](https://mcp.tempo.xyz)
* [MPP](https://mpp.dev/)
