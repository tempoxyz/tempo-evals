# Tempo Bench

Minimal Harbor-based benchmark for measuring whether Tempo docs and agent tools
help agents build real Tempo integrations.

The current V0 covers baseline payments plus additional Tempo integration
surfaces:

- `tempo/transfer-with-memo`: baseline task with the prompt and fixture env.
- `tempo/transfer-with-memo-docs-mcp`: same task with a Tempo docs MCP sidecar.
- `tempo/transfer-with-memo-fee-payer`: memo transfer using fee sponsorship.
- `tempo/set-fee-token`: persistent fee token preference via Fee Manager.
- `tempo/create-stablecoin-with-policy`: TIP-20 creation plus TIP-403 policy.
- `tempo/faucet-funded-transfer`: faucet funding followed by AlphaUSD transfer.
- `tempo/stablecoin-dex-swap`: Stablecoin DEX liquidity plus swap execution.

Each asks for a TypeScript script against Tempo localnet. The verifier
independently builds and runs the submission, then checks localnet for the
expected onchain event.

## Layout

```text
.
├── job.yaml
├── job.agents.yaml
├── scripts/
│   └── sync-shared.mjs
├── shared/
│   ├── docker/
│   │   ├── compose/
│   │   ├── main-node/
│   │   └── tempo-localnet/
│   ├── mcp/
│   │   └── tempo-docs/
│   ├── rewardkit/
│   └── verifier/
│       ├── bin/tempo-bench-verify.js
│       └── src/
└── tasks/
    ├── dataset.toml
    ├── README.md
    ├── transfer-with-memo/
    ├── transfer-with-memo-docs-mcp/
    ├── transfer-with-memo-fee-payer/
    ├── set-fee-token/
    ├── create-stablecoin-with-policy/
    ├── faucet-funded-transfer/
    └── stablecoin-dex-swap/
        ├── instruction.md
        ├── task.toml
        ├── environment/
        ├── solution/
        └── tests/
```

`shared/` is the source of truth for reusable code. Harbor tasks still need to
be self-contained, so `scripts/sync-shared.mjs` links reusable sidecar assets
where Harbor can follow symlinks and copies the small per-task pieces where
Docker/Harbor require files inside the task context.

## Harbor Concepts

- `job.yaml` is the Harbor oracle baseline job. It selects the local Docker
  environment, the `oracle` agent, and the `tasks/` dataset.
- `job.agents.yaml` is the local harness matrix for real agents. It currently
  runs `codex` and `claude-code` over the same dataset.
- `tasks/dataset.toml` is the Harbor dataset manifest for the future
  `tempo/tempo-bench` benchmark.
- `tasks/*/task.toml` is the task config. This is the main place to change
  fixture values, verifier case, timeouts, MCP servers, and environment
  resources.
- `tasks/*/task.toml` sets `[verifier].environment_mode = "shared"` explicitly.
  The verifier needs the submitted app, live localnet sidecars, and the same
  service network. Harbor's separate verifier mode is useful for artifact-only
  grading, but would add collect/artifact plumbing here.
- `tasks/*/instruction.md` is the agent-facing prompt.
- `tasks/*/environment/docker-compose.yaml` adds task sidecars. It is linked
  from `shared/docker/compose/`. Harbor owns the `main` service and merges this
  file into its base Compose config.
- `tasks/*/environment/Dockerfile` is copied from `shared/docker/main-node/`.
  BuildKit expects the Dockerfile inside the build context, so this cannot be a
  symlink to a shared file outside the task. Test-only Python packages are not
  baked into this image; `tests/test.sh` installs the pinned RewardKit package
  during verification, matching Harbor's quality rubric.
- `tasks/transfer-with-memo-docs-mcp` also declares a `tempo-docs` MCP server in
  `task.toml` and runs it as the `tempo-docs-mcp` Compose sidecar.
- `tasks/*/tests/test.sh` is Harbor's verifier entrypoint. It runs RewardKit,
  which discovers the task-local criteria in `tests/criteria/check.py`, then
  writes `/logs/verifier/reward.json`.
  `tests/reward.toml` is intentionally task-local and uses `threshold = 1.0`,
  so final `reward` is `1` only when every explicit file, regex, docs-usage,
  and e2e criterion passes. The e2e criterion runs
  `tests/e2e/verify-tempo.sh`, which is copied from shared code because Harbor
  mounts `/tests` without following external symlink targets.
- `tasks/*/tests/tempo-bench-verifier` is a minimal copied verifier package
  containing only the shared core plus the task's selected case. Harbor mounts
  `/tests` without following external package symlinks, so the package must be
  copied into each task.
- `tasks/*/solution/solve.sh` is used only by Harbor's `oracle` agent for sanity
  checks. Each `solution/` is a normal minimal TypeScript app
  (`package.json`, `tsconfig.json`, `src/index.ts`); `solve.sh` just copies that
  app into `/app`.

## Configuration

The task TOML keeps Tempo fixture values in `[environment.env]`:

```toml
TEMPO_BENCH_CASE = "transfer-with-memo"
TEMPO_RPC_URL = "http://tempo-localnet:8545"
TEMPO_TOKEN = "0x20c0000000000000000000000000000000000001"
TEMPO_PAYER_PRIVATE_KEY = "..."
TEMPO_RECIPIENT = "0x1111111111111111111111111111111111111111"
TEMPO_AMOUNT = "0.17"
TEMPO_MEMO = "TEMPO-EVAL-001"
TEMPO_DECIMALS = "6"
```

The instruction tells the agent to read these values from environment variables.
Because the verifier runs in shared mode, Harbor's verifier command inherits the
same `main` container environment. The shared compose templates inject the
`[environment.env]` keys into that container, so fixture values still have one
source of truth. The verifier records the starting block, runs the submission,
and verifies the onchain event independently of anything the submission writes.

Run `make sync` after changing task config. The sync script
also checks that `[verifier.env]` stays absent for shared-mode tasks, avoiding
duplicated fixture maps.

## Development Loop

Install Harbor:

```bash
uv tool install harbor
```

Install RewardKit for local parity with Harbor verifier runs:

```bash
uv tool install harbor-rewardkit==0.1.7
```

Sync shared code into tasks:

```bash
make sync
```

Refresh task digests in the dataset:

```bash
make dataset
```

Run the default model benchmark:

```bash
make benchmark
```

This defaults to:

```bash
make benchmark AGENT=claude-code MODEL=haiku
```

Run the oracle baseline:

```bash
make benchmark-oracle
```

Run the Codex and Claude Code harness matrix:

```bash
make benchmark-agents
```

Run a different harness/model over all tasks:

```bash
make benchmark AGENT=claude-code MODEL=sonnet
```

Run a single harness/model over matching tasks:

```bash
make benchmark AGENT=claude-code MODEL=sonnet TASK_FILTER='tempo/transfer-*'
```

Open Harbor's viewer:

```bash
make view
```

Run the local checks used before benchmarking:

```bash
make check
```

## Agent Harnesses

Harbor runs one trial per task per configured agent. Add built-in agents under
`agents:` in `job.agents.yaml`:

```yaml
agents:
  - name: codex
  - name: claude-code
```

This Harbor install lists `codex` and `claude-code` as built-ins. It does not
list `amp`; to add AMP, wrap it as a Harbor custom agent and set
`import_path: module.path:ClassName`, or use an ACP registry shorthand if AMP
ships an ACP adapter.

For ad hoc model runs, use `make benchmark`. It is a thin wrapper over
`harbor run --path tasks --agent ... --model ...`.

Common examples:

```bash
# Claude Code with latest Haiku over all tasks
make benchmark

# Claude Code with Sonnet over all tasks
make benchmark MODEL=sonnet

# Codex with an explicit model
make benchmark AGENT=codex MODEL=gpt-5

# Only transfer tasks
make benchmark TASK_FILTER='tempo/transfer-*'

# One matching task, useful for smoke tests
make benchmark TASK_FILTER='tempo/set-*' N_TASKS=1

# Custom job name
make benchmark JOB_NAME=tempo-bench-claude-haiku-smoke N_TASKS=1

# Oracle baseline
make benchmark-oracle
```

`TASK_FILTER` is passed to Harbor's `--include-task-name` and supports glob
patterns. `N_TASKS` limits the task count after filtering. `benchmark-model` is
kept as an alias for `benchmark`:

```bash
make benchmark-model AGENT=codex MODEL=gpt-5 TASK_FILTER='tempo/set-*' N_TASKS=1
```

## Adding Pieces

Add a task:

1. Copy `tasks/transfer-with-memo` to a new task directory.
2. Update `task.toml` name, metadata, fixture env, and `TEMPO_BENCH_CASE`.
3. Update `instruction.md`.
4. Run `make sync`.
5. Run `harbor add ./tasks/<task-dir> --to tasks`.

Add a verifier:

1. Add a case file under `shared/verifier/src/cases/`.
2. Export it from `shared/verifier/src/cases/index.js`.
3. Set `TEMPO_BENCH_CASE` in the task TOML.
4. Run `make sync`.

Add an MCP profile:

1. Add the MCP server under `shared/mcp/` if it is reusable.
2. Add the MCP server as a sidecar in the task's `environment/docker-compose.yaml`.
3. Declare it in `task.toml` using Harbor's `[[environment.mcp_servers]]`.
4. Keep the fixture and verifier unchanged unless the actual task changes.
5. Run `make sync`.

Add a metric:

1. Compute it in `shared/verifier/src/index.js` or the relevant case verifier.
2. Include it in the internal verifier score file.
3. Keep `reward` as the primary Harbor score.

## Score

RewardKit writes Harbor's score file:

```json
{
  "reward": 1
}
```

The Tempo verifier also writes detailed component scores to
`/logs/verifier/tempo-bench-scores.json`, including `build`, `run`, and
`onchain`. `reward` is `1` only when the submission builds, runs, and the
verifier observes the expected onchain evidence on Tempo localnet. RewardKit
also writes `/logs/verifier/reward-details.json`, listing each explicit
built-in criterion and its pass/fail score.
