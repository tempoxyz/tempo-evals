# Tempo Evals

Evaluation harnesses for agents building on Tempo and related protocols,
powered by [Harbor](https://harborframework.com).

## Suites

| Suite | Status | Dataset | What it measures | Guide |
| --- | --- | --- | --- | --- |
| Tempo integration | v1 | `tempo/tempo-bench-v1` | TypeScript integrations that submit and verify Tempo testnet transactions | [tasks/tempo-v1](tasks/tempo-v1/README.md) |
| Tempo MCP efficiency | v1 | `tempo/tempo-mcp-bench-v1` | Live Tempo investigations using direct documentation tools or `docs_code` | [tasks/tempo-mcp-v1](tasks/tempo-mcp-v1/README.md) |
| MPP integration | Unstable | `tempo/mpp-bench-v1` | Paid HTTP and MCP services and clients on Tempo testnet | [tasks/mpp](tasks/mpp/README.md) |

Suite guides own suite-specific behavior and commands. Task `README.md` files
are short Harbor Hub descriptions; `instruction.md` files are the agent-facing
contracts.

## How It Works

- A **task** contains an instruction, environment, oracle solution, and
  independent verifier.
- The **oracle** proves that the task is solvable. It is never shown to agents.
- The **verifier** deterministically checks the submission and writes the
  Harbor reward. RewardKit quality signals are reported separately and cannot
  replace functional correctness.
- A **dataset** is a versioned task collection. Its task set, prompts, fixtures,
  verifier behavior, and scoring are fixed within a benchmark major.
- A **job** runs one or more agent trials against a dataset. Job configs are
  compiled from `config/` rather than edited by hand.

### Runtime Isolation

Each task uses two images generated from the refs in `config/tasks.yaml`:

- The agent image contains only the task runtime.
- The verifier image extends the exact agent image and adds RewardKit and the
  shared Tempo verifier.

Harbor runs them in separate environments and transfers only the task's
declared artifacts into the verifier. CI publishes the pair under write-once
source tags; remote runs resolve both tags to immutable digests.

### Access Profiles

Tempo integration tasks use the same task artifacts under two access profiles:

| Profile | Agent access |
| --- | --- |
| `docs` | Tempo documentation pinned by `config/tempo-docs.lock.json` |
| `mcp` | The same pinned documentation plus the Tempo API MCP server |

The Tempo MCP efficiency suite instead uses `mcp-direct` and `mcp-code` to
compare direct documentation tools with `docs_code`; both query live Tempo data
and documentation.

> [!IMPORTANT]
> **OpenAI documentation exception:** OpenAI models run through Codex's hosted
> web fetch, which resolves `docs.tempo.xyz` outside the task sandbox. They
> therefore use the live public docs and do not honor
> `config/tempo-docs.lock.json` or `--docs-sha`. The pin only controls
> documentation requests routed from within the sandbox.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `tasks/` | Authored, versioned Harbor task suites |
| `shared/` | Shared runtime images, verifiers, and suite harnesses |
| `config/` | Benchmark identities, access profiles, model matrices, and job sources |
| `scripts/` | Synchronization, execution, validation, and result tooling |

## Setup

Requirements: Docker, Node.js with `npm`, and
[`uv`](https://docs.astral.sh/uv/).

```bash
npm ci --ignore-scripts --no-audit --no-fund
uv sync
npm run docs:prepare
```

Copy [`.env.example`](.env.example) to `.env` and populate only the credentials
needed for the runner you use. Never commit `.env` or a funded private key.

For remote runs, install Harbor with Daytona support:

```bash
uv tool install 'harbor[daytona]'
```

## Run Benchmarks

```bash
# Validate a suite with its oracle.
npm run bench:local:oracle -- --task-suite tempo

# Iterate on one task.
npm run bench:local:one -- --task-filter tempo-v1/transfer-with-memo

# Run an agent against one Tempo task with Docs plus MCP.
npm run bench:local:agent:dev -- \
  --task-suite tempo --profile mcp --task-filter transfer-with-memo
```

Daytona runs require credentials and the paired CI-published image refs:

```bash
AGENT_IMAGE="$(npm run -s agent-image:ref)"
VERIFIER_IMAGE="$(npm run -s verifier-image:ref)"

# Development model matrix: one attempt per task.
npm run bench:matrix:dev -- \
  --task-suite tempo --profile all \
  --agent-image "$AGENT_IMAGE" --verifier-image "$VERIFIER_IMAGE"

# Production model matrix: three attempts per task.
npm run bench:matrix:production -- \
  --task-suite tempo --profile all \
  --agent-image "$AGENT_IMAGE" --verifier-image "$VERIFIER_IMAGE"
```

The image-ref commands fail until CI has published both images, then return
immutable digest refs. Trusted same-repository pull requests and `main` may
publish; fork pull requests only build the pair.

The matrix commands read `config/models.dev.yaml` and
`config/models.production.yaml`. `--profile all` runs the `docs` and `mcp` jobs
in parallel. `--concurrency` limits trials per profile job, so a value of 32 can
run 64 trials across the pair. `--agent-concurrency` overrides the per-provider,
per-profile model caps.

Production model configs pin the candidate and judge model IDs. The runner also
requires a clean checkout and a full docs SHA, then records `TEMPO_EVALS_SHA`
and `TEMPO_DOCS_SHA` in Harbor's generated `lock.json`. Production runs retry
transient trial and setup failures up to four times by default; use
`--max-retries` to override that limit.

Jobs are written under `jobs/` and are not uploaded automatically:

```bash
npm run harbor:view
uv run harbor auth login # Skip when already authenticated.
uv run harbor upload --public "jobs/<job-name>"
```

## Develop Tasks

Read the relevant suite guide before editing a task. The usual workflow is:

1. Scaffold with `npm run task:new -- --suite <suite> --name <task>`.
2. Define the prompt and metadata in `instruction.md` and `task.toml`.
3. Add the minimal environment, independent verifier, and oracle solution.
4. Run a clean local oracle for the affected suite.
5. Refresh generated artifacts with `npm run dataset`, then run
   `npm run check`.

Useful repository-wide commands:

```bash
npm run sync             # Refresh shared assets and generated job configs.
npm run task:lint        # Validate task structure, metadata, and canaries.
npm run check:generated  # Check generated artifacts are current.
npm run check            # Run the full repository check.
npm run clean            # Remove local job output and staging caches.
```

Do not hand-edit generated configs or synchronized MPP harness files. See
[AGENTS.md](AGENTS.md) for source ownership, benchmark versioning, validation,
and contribution rules.

## Environment

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude Code runs and RewardKit evaluation |
| `OPENAI_API_KEY` | Codex runs |
| `DAYTONA_API_KEY` | Daytona authentication |
| `DAYTONA_JWT_TOKEN` + `DAYTONA_ORGANIZATION_ID` | Alternative Daytona authentication |
| `HARBOR_API_KEY` | Optional noninteractive Harbor Hub authentication |
| `TEMPO_MCP_EVAL_URL` | Optional MCP efficiency suite upstream override |

## References

- [Harbor concepts](https://www.harborframework.com/docs/core-concepts)
- [Tempo documentation](https://docs.tempo.xyz/)
- [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for task-authoring and validation
requirements. Report vulnerabilities according to [SECURITY.md](SECURITY.md),
not through public issues.

## License

Tempo Evals is dual-licensed under [Apache-2.0](LICENSE-APACHE) and
[MIT](LICENSE-MIT), at your option.
