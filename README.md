# Tempo Bench

Tempo Bench is a Harbor benchmark for testing whether agents can build real
Tempo localnet integrations from pinned docs or the Tempo MCP server.

Each task asks an agent to create a minimal TypeScript app in `/app`. Harbor
starts the task environment, runs the agent, runs the verifier in the same
localnet environment, and records a binary `reward`.

## Task Matrix

Each intent has two access profiles:

| Intent | Docs task | MCP task |
| --- | --- | --- |
| Transfer with memo | `tempo/transfer-with-memo-docs` | `tempo/transfer-with-memo-mcp` |
| Transfer with fee payer | `tempo/transfer-with-memo-fee-payer-docs` | `tempo/transfer-with-memo-fee-payer-mcp` |
| Set fee token | `tempo/set-fee-token-docs` | `tempo/set-fee-token-mcp` |
| Create stablecoin with policy | `tempo/create-stablecoin-with-policy-docs` | `tempo/create-stablecoin-with-policy-mcp` |
| Faucet-funded transfer | `tempo/faucet-funded-transfer-docs` | `tempo/faucet-funded-transfer-mcp` |
| Stablecoin DEX swap | `tempo/stablecoin-dex-swap-docs` | `tempo/stablecoin-dex-swap-mcp` |

The docs profile exposes a local HTTP docs sidecar at
`TEMPO_DOCS_URL=http://tempo-docs:3000/developers`. The sidecar is generated
from the locked `tempoxyz/docs` commit in `config/tempo-docs.lock.json` and
serves public-compatible agent docs routes such as `/developers/llms.txt`,
`/developers/llms-full.txt`, and `/developers/docs/*.md`. The MCP profile
configures the remote `tempo` MCP server at `https://mcp.tempo.xyz`.

## Structure

| Path | Purpose |
| --- | --- |
| `config/job.local.*.yaml` | Local Docker Harbor jobs. |
| `config/job.daytona.*.yaml` | Daytona DinD Harbor jobs. |
| `config/tempo-docs.lock.json` | Pinned `tempoxyz/docs` commit used by docs-profile tasks. |
| `scripts/prepare-docs-bundle.mjs` | Builds the local static docs bundle under `.cache/tempo-docs/<sha>/public`. |
| `scripts/run-benchmark.ts` | Single entrypoint for sync, dataset refresh, checks, local runs, Daytona runs, and cleanup. |
| `scripts/create-daytona-dind-snapshot.py` | Optional helper for creating reusable Daytona DinD snapshots. |
| `scripts/sync-shared.mjs` | Generates docs/MCP task variants and syncs shared verifier/assets into task contexts. |
| `shared/` | Source of truth for reusable Docker, verifier, RewardKit, MCP, and localnet code. |
| `tasks/` | Harbor dataset and task directories. Some shared assets are intentionally symlinked. |

Daytona runs need complete task upload contexts. Do not copy generated shared
assets into `tasks/`. `scripts/run-benchmark.ts` handles this by staging a
temporary dereferenced task tree under `.cache/harbor-daytona/<job>/tasks` and
rewriting the Harbor config to point at that staged tree.

## Harbor Mapping

| Harbor concept | Where it lives here |
| --- | --- |
| Dataset | `tasks/dataset.toml` |
| Task | `tasks/*/task.toml`, `instruction.md`, `environment/`, `tests/`, `solution/` |
| Job | `config/job.*.yaml` |
| Agent | `oracle` or `claude-code` in the job config |
| Environment | Local Docker or Daytona DinD |
| Verifier | `tasks/*/tests/test.sh` plus shared verifier code copied from `shared/` |
| Score | `/logs/verifier/reward.json` with `{"reward": 0|1}` |

The verifier runs in Harbor shared-environment mode so it can inspect the
submitted app and the same Tempo localnet used by the agent. RewardKit
correctness/quality outputs are diagnostic; the primary Harbor reward follows
the independent build/run/onchain verifier result.

## Jobs

| Command | Config | Runtime | Attempts | Purpose |
| --- | --- | --- | ---: | --- |
| `npm run bench:local:oracle` | `config/job.local.oracle.yaml` | Docker | 1 | Validate oracle solutions locally. |
| `npm run bench:local:agent` | `config/job.local.agent.yaml` | Docker | 3 | Full local Claude Code matrix. |
| `npm run bench:local:agent:dev` | `config/job.local.agent.dev.yaml` | Docker | 1 | Local smoke run. |
| `npm run bench:daytona:oracle` | `config/job.daytona.oracle.yaml` | Daytona | 1 | Validate oracle solutions remotely. |
| `npm run bench:daytona:agent` | `config/job.daytona.agent.yaml` | Daytona | 3 | Full remote Claude Code matrix. |
| `npm run bench:daytona:agent:dev` | `config/job.daytona.agent.dev.yaml` | Daytona | 1 | Remote smoke run. |

Use the generic model runner for one-off local runs:

```bash
npm run bench:model -- --model sonnet --task-filter 'tempo/transfer-*'
```

## Setup

Install project tools:

```bash
npm install
uv sync
```

Prepare the pinned docs bundle:

```bash
npm run docs:prepare
```

Optional global Harbor install:

```bash
uv tool install 'harbor[daytona]'
```

Create `.env` with the runtime credentials you need:

| Key | Used for |
| --- | --- |
| `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` | Claude Code and RewardKit LLM judging. |
| `CLAUDE_CODE_OAUTH_TOKEN` | Claude Code subscription auth. |
| `CLAUDE_FORCE_OAUTH` | Optional Claude Code OAuth forcing; use `1`/`true`, not an empty value. |
| `DAYTONA_API_KEY` | Daytona runs. |
| `DAYTONA_TARGET` | Optional Daytona target. |

The checked-in Daytona configs start from `docker:28.3.3-dind` directly. If you
want to experiment with snapshot-backed startup later, create a snapshot with
`uv run scripts/create-daytona-dind-snapshot.py --recreate-error` and set
`environment.kwargs.dind_snapshot` in the Daytona config.

## Run

Refresh generated task files and Harbor digests:

```bash
npm run dataset
```

Run local jobs:

```bash
npm run bench:local:oracle
npm run bench:local:agent:dev
npm run bench:local:agent
```

Run Daytona jobs:

```bash
npm run bench:daytona:oracle
npm run bench:daytona:agent:dev
npm run bench:daytona:agent
```

Override concurrency:

```bash
npm run bench:daytona:agent -- --concurrency 4 --agent-concurrency 2
```

Daytona runs default to two retries for transient remote Docker startup
failures in a fresh sandbox.

Run a single task through a config-backed Daytona job:

```bash
npm run bench:daytona:agent:dev -- --task-filter transfer-with-memo-mcp --concurrency 1 --agent-concurrency 1
```

Use a stable job name:

```bash
npm run bench:local:agent -- --job-name tempo-bench-agents-local
```

Open Harbor's job viewer:

```bash
npm run harbor:view
```

## Checks

```bash
npm run check
npm run check:dataset
npm run check:generated
```

Clean local outputs:

```bash
npm run clean
```

## Editing

- Edit source task intents under `tasks/<intent>/`.
- Edit shared verifier, RewardKit, localnet, or Docker code under `shared/`.
- Run `npm run sync` after task/shared edits.
- Run `npm run dataset` after changes that should update Harbor task digests.
- Keep Daytona configs thin. If Daytona upload behavior needs to change, update
  `scripts/run-benchmark.ts` staging logic instead of committing staged task
  copies.

## References

- [Harbor docs](https://www.harborframework.com/docs/core-concepts)
- [Harbor GitHub](https://github.com/harbor-framework/harbor)
- [Daytona snapshots](https://www.daytona.io/docs/en/snapshots/)
- [Tempo docs](https://docs.tempo.xyz/)
- [Tempo MCP server](https://mcp.tempo.xyz)
