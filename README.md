# Tempo Evals

Monorepo for tooling and evaluation harnesses targeting Tempo and related protocols.

Powered by [Harbor](https://harborframework.com).

## Suites

| Suite | Dataset | Version | What it measures | Suite guide |
| --- | --- | --- | --- | --- |
| Tempo integration | `tempo/tempo-bench-v1` | `v1` | TypeScript integrations that submit and verify Tempo testnet transactions | [tasks/tempo-v1](tasks/tempo-v1/README.md) |
| Tempo MCP efficiency | `tempo/tempo-mcp-bench-v1` | `v1` | Live Tempo data investigations using direct documentation tools or `docs_code` | [tasks/tempo-mcp-v1](tasks/tempo-mcp-v1/README.md) |
| MPP integration | `tempo/mpp-bench-v1` | `v1` | Paid HTTP and MCP services and clients on Tempo testnet | [tasks/mpp](tasks/mpp/README.md) |

Each suite README owns its task model, harness behavior, run commands, and
implementation notes. Task-level `README.md` files are concise Harbor Hub
descriptions; `instruction.md` files are the agent-facing contracts.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `tasks/` | Authored, versioned Harbor task suites |
| `shared/` | Reusable base image, verifiers, and suite harness assets |
| `config/` | Dataset identities, access profiles, run variants, and generated jobs |
| `scripts/` | Task synchronization, benchmark execution, validation, and result tools |

## Key Concepts

Harbor terms used throughout this repository:

- **Task** — a single instruction, container environment, and test script,
  authored as a directory (`instruction.md`, `task.toml`, `environment/`,
  `solution/`, `tests/`). The instruction and verifier behavior form the
  evaluation contract.
- **Oracle** — the minimal reference solution checked in under `solution/`.
  Oracle runs execute it in place of an agent to prove the task is solvable
  and the verifier accepts a correct submission. It is not shown to agents.
- **Verifier** — the independent test script under `tests/` that checks the
  submission programmatically and writes the Harbor reward. Correctness must
  be deterministic; RewardKit quality checks are diagnostic signals layered on
  top, never a substitute.
- **Dataset** — a versioned collection of tasks; each suite here is one
  dataset (e.g. `tempo/tempo-bench-v1`) with a checked-in generated manifest
  (`dataset.toml`). A dataset major is an immutable evaluation contract.
- **Trial and job** — a trial is one agent attempt at a task producing a
  reward; a job is a batch of trials. Jobs here are compiled from `config/`
  into `config/generated/` rather than written by hand.
- **Access profile** — run-time injection of documentation or MCP access into
  a job, configured in `config/tasks.yaml`, so the same task artifact can be
  evaluated under different capabilities.

## Setup

### Requirements

* Docker
* Node.js with `npm`
* [uv](https://docs.astral.sh/uv/).

### Instructions

```bash
uv sync
npm run docs:prepare
```

Install Harbor with Daytona support when you need remote runs:

```bash
uv tool install 'harbor[daytona]'
```

## Global Workflows

```bash
# Synchronize shared assets and generated job configurations.
npm run sync

# Validate task conventions, generated assets, scripts, tests, formatting, and lint.
npm run check

# Create a task scaffold in a named suite.
npm run task:new -- --suite tempo --name example-task

# Remove local job output and staging caches.
npm run clean
```

Run the dataset refresh command after changing task files. Dataset manifests are checked-in generated artifacts and must stay in sync with their suite.

## Shared Architecture

Three shared layers keep the suites consistent:

- **One base image.** Every task environment extends the base image configured
  in `config/tasks.yaml`, which bundles the RewardKit environment and the
  shared Tempo verifier.
- **Injected access profiles.** Benchmark jobs grant documentation or MCP
  access at run time instead of baking it into task source, so the same task
  artifact can be evaluated under different profiles. Profiles are configured
  centrally in `config/tasks.yaml`; see the suite guides for profile-specific
  behavior.
- **Immutable benchmark majors.** A dataset version fixes its task set,
  prompts, verifier behavior, and scoring. Changes that make results
  incomparable require a new dataset version rather than an in-place rewrite.

## Running Tasks

Every run is a Harbor job compiled from `config/`; the npm scripts select the
variant. Suite READMEs cover suite-specific filters and workflows.

### Locally

Local runs use Docker and build the shared base image from the checkout, so
they only need the API keys listed under Environment.

```bash
# Oracle validation for one suite.
npm run bench:local:oracle -- --task-suite tempo

# Fast iteration on a single task.
npm run bench:local:one -- --task-filter tempo-v1/transfer-with-memo

# Agent smoke run with the MCP profile.
npm run bench:local:agent:dev -- --task-suite tempo --profile mcp
```

### On Daytona

Daytona runs execute the same jobs on remote sandboxes. They require Daytona
credentials and an explicit CI-published base image passed with `--base-image`;
`npm run base-image:ref` prints the immutable reference for the current
checkout.

```bash
# Oracle validation on Daytona.
npm run bench:daytona:oracle -- --base-image "$(npm run -s base-image:ref)"

# Full Claude Code matrix on Daytona.
npm run bench:daytona:agent -- --base-image "$(npm run -s base-image:ref)"
```

## Authoring a New Task

Read the suite README first; each suite has its own task model and shared
files. The general flow:

1. **Scaffold.** `npm run task:new -- --suite <suite> --name <task>` creates
   the task directory with the suite's conventions in place.
2. **Write the contract.** `instruction.md` is the agent-facing prompt: keep
   it concise and unambiguous, and prefer observable outputs (files, logs,
   onchain effects) that a verifier can check. `task.toml` declares metadata,
   resources, and verifier configuration.
3. **Build the environment.** `environment/Dockerfile` extends the shared
   base image; add only what the task needs.
4. **Write the verifier.** `tests/` must establish correctness independently
   and deterministically — it defines what "solved" means. Follow existing
   verifier patterns and use the smallest check set that proves the
   integration works. RewardKit quality checks go in `tests/quality/` as
   diagnostics on top.
5. **Write the oracle.** `solution/` is the minimal solution that satisfies
   the instruction. If the oracle cannot pass the verifier, the task is
   broken; if it passes trivially without doing the work, the verifier is too
   weak.
6. **Validate and refresh artifacts.** Run `npm run task:lint`, then a clean
   local oracle run (`npm run bench:local:oracle -- --task-suite <suite>`),
   then refresh the suite's dataset manifest with `npm run dataset`. Commit
   the manifest and any generated artifacts with the task. `npm run check`
   runs the full repository validation.

Adding a task to a released benchmark major changes the evaluation contract;
see [AGENTS.md](AGENTS.md) for versioning and contribution rules.

## Environment

| Variable | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Claude Code runs and RewardKit LLM evaluation |
| `OPENAI_API_KEY` | Codex production runs |
| `DAYTONA_API_KEY` | Daytona authentication; JWT variables are an alternative |
| `DAYTONA_JWT_TOKEN` + `DAYTONA_ORGANIZATION_ID` | Daytona JWT authentication |
| `DAYTONA_TARGET` | Optional Daytona target |
| `TEMPO_MCP_EVAL_URL` | Optional upstream endpoint for the MCP efficiency bridge |

## References

* [Harbor concepts](https://www.harborframework.com/docs/core-concepts)
* [Tempo documentation](https://docs.tempo.xyz/)
* [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)
