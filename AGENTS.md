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
npm run check               # Type-check scripts, format check, lint
npm run check:scripts       # TypeScript type check
npm run check:dataset       # Verify Tempo dataset digest freshness
npm run check:generated     # Verify generated Tempo output freshness
npm run clean               # Remove job/cache output
```

## Jobs

```bash
npm run bench:local:oracle       # Local Docker oracle validation
npm run bench:local:agent:dev    # Local Docker agent smoke
npm run bench:local:agent        # Full local Docker agent run
npm run bench:daytona:oracle     # Daytona oracle validation
npm run bench:daytona:agent:dev  # Daytona agent smoke
npm run bench:daytona:agent      # Full Daytona agent run
```

Single task:

```bash
npm run bench:daytona:agent:dev -- --task-filter transfer-with-memo-mcp --concurrency 1 --agent-concurrency 1
```

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

Do not hand-edit generated Tempo variants:

- `tasks/*-docs/`
- `tasks/*-mcp/`

Change the base task or generator, then run:

```bash
npm run sync

# if you want to sync all tasks
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
