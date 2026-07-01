# Tempo Bench

Minimal Harbor-based benchmark for measuring whether Tempo docs and agent tools
help agents build real Tempo integrations.

The current V0 covers six Tempo integration intents across two access profiles:

- `tempo/transfer-with-memo-docs` / `tempo/transfer-with-memo-mcp`
- `tempo/transfer-with-memo-fee-payer-docs` / `tempo/transfer-with-memo-fee-payer-mcp`
- `tempo/set-fee-token-docs` / `tempo/set-fee-token-mcp`
- `tempo/create-stablecoin-with-policy-docs` / `tempo/create-stablecoin-with-policy-mcp`
- `tempo/faucet-funded-transfer-docs` / `tempo/faucet-funded-transfer-mcp`
- `tempo/stablecoin-dex-swap-docs` / `tempo/stablecoin-dex-swap-mcp`

`scripts/sync-shared.mjs` materializes each intent into two task variants:

- `-docs`: exposes `TEMPO_DOCS_URL=https://docs.tempo.xyz/`.
- `-mcp`: configures the official MCP server at
  `https://mcp.tempo.xyz`.

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
    ├── transfer-with-memo-docs/
    ├── transfer-with-memo-mcp/
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

- `job.yaml` is the Harbor sanity-check job. It selects the local Docker
  orchestrator, the `oracle` agent, and the `tasks/` dataset.
- `job.agents.yaml` is the local harness matrix for real agents. It currently
  runs `claude-code` over the docs and mcp task variants.
- `tasks/dataset.toml` is the Harbor dataset manifest for the future
  `tempo/tempo-bench` benchmark.
- `tasks/*/task.toml` is the task config. This is the main place to change
  fixture values, verifier case, timeouts, MCP servers, and environment
  resources. Generated tasks currently use public Docker networking so agent
  setup, package installs, docs access, and the remote MCP endpoint can all
  work reliably.
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
  symlink to a shared file outside the task. `make sync` also materializes the
  ignored `tasks/*/environment/rewardkit-package/` build-context copy so the
  image can bake in the shared Tempo RewardKit helpers.
- `tasks/*-mcp` declares the official remote `tempo` MCP server in
  `task.toml`. No local docs MCP sidecar is used for the main matrix.
- `tasks/*/tests/test.sh` is Harbor's verifier entrypoint. It runs RewardKit,
  writes RewardKit's dimension output to `/logs/verifier/rewardkit-output.json`,
  writes dimension details to `/logs/verifier/reward-details.json`, and writes
  Harbor's primary `/logs/verifier/reward.json` as exactly one binary key:
  `reward`.
- `shared/rewardkit-package` defines reusable RewardKit criteria for Tempo
  TypeScript project shape, source-pattern checks, trajectory checks, and the
  onchain verifier. The package is installed into the task image as
  `tempo_bench_rewardkit`.
- `tasks/*/tests/correctness` registers task-specific source patterns plus the
  shared build/run/onchain checks. These criteria are diagnostic; Harbor's
  binary `reward` follows the independent Tempo verifier's build/run/onchain
  result.
- `tasks/*/tests/quality` contains non-binary quality scoring. It combines
  cutoff-based turn/token efficiency checks with a Claude Haiku LLM judge over
  the submitted TypeScript files. Raw efficiency counts are written to
  `/logs/verifier/efficiency.json`. Quality does not affect Harbor's binary
  pass/fail reward. Local runs without `ANTHROPIC_API_KEY` or
  `ANTHROPIC_AUTH_TOKEN` skip the LLM quality reward and write
  `/logs/verifier/quality-skipped.txt`. If the LLM judge returns an unparsable
  response, the verifier reruns the programmatic rewards without the LLM judge
  so primary scoring and efficiency metrics still get written.
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

Efficiency score cutoffs are configurable per task through `[environment.env]`:

```toml
TEMPO_BENCH_TURNS_SCORE_CUTOFFS = "20=1.0,40=0.8,60=0.5,80=0.2,*=0.0"
TEMPO_BENCH_TOKENS_SCORE_CUTOFFS = "250000=1.0,500000=0.8,1000000=0.5,1500000=0.2,*=0.0"
```

The first cutoff whose max is greater than or equal to the measured value wins;
`*` is the fallback score.

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

Run the Claude Code harness matrix:

```bash
make benchmark-agents
```

Benchmark Make targets run Harbor with one concurrent trial per detected logical
CPU by default. Override this if Docker Desktop, memory, API limits, or localnet
load become the bottleneck:

```bash
make benchmark-agents N_CONCURRENT=4
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

Harbor runs three attempts per task per configured agent in `job.agents.yaml`.
The checked-in agent job is Claude Code only, defaults to Haiku, and passes auth
from the host env. The verifier also receives Anthropic auth so the RewardKit
quality judge can run Claude Haiku:

```yaml
agents:
  - name: claude-code
    model_name: claude-haiku-4-5
    env:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
      ANTHROPIC_AUTH_TOKEN: ${ANTHROPIC_AUTH_TOKEN:-}
      CLAUDE_CODE_OAUTH_TOKEN: ${CLAUDE_CODE_OAUTH_TOKEN:-}
      CLAUDE_FORCE_OAUTH: ${CLAUDE_FORCE_OAUTH:-false}
```

`make benchmark-agents` runs `make check-agent-auth` first. Without one of
`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, or `CLAUDE_CODE_OAUTH_TOKEN`,
Claude Code exits before writing `/app/package.json` or `/app/src`, and Harbor's
artifact collection reports Docker copy errors for those missing paths.
The RewardKit quality judge requires `ANTHROPIC_API_KEY` or
`ANTHROPIC_AUTH_TOKEN` in the verifier environment. Without one, local verifier
runs skip the LLM quality reward and still report the binary correctness reward.
If using `CLAUDE_FORCE_OAUTH`, set it to `1`/`true` or leave it unset; an empty
value is invalid.

Agent benchmarks use a timestamped `AGENT_JOB_NAME` by default so changing
`job.agents.yaml` does not collide with an existing `jobs/` directory. Override
`AGENT_JOB_NAME=tempo-bench-agents-local` only when intentionally reusing a
stable job name with the same config.

This Harbor install lists `claude-code` as a built-in. It does not list `amp`;
to add AMP, wrap it as a Harbor custom agent and set
`import_path: module.path:ClassName`, or use an ACP registry shorthand if AMP
ships an ACP adapter.

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

Add an access profile:

1. Update `profiles` in `scripts/sync-shared.mjs`.
2. Add any profile-specific TOML, instruction, and criteria rewrites there.
3. Keep the fixture and verifier unchanged unless the actual task changes.
4. Run `make sync`.

Add a metric:

1. Compute it in `shared/verifier/src/index.js` or the relevant case verifier.
2. Include it in the internal verifier score file.
3. Keep `reward` as the primary Harbor score.

## Score

RewardKit writes Harbor's score file:

```json
{"reward":1}
```

The Tempo verifier writes detailed component scores to
`/logs/verifier/tempo-bench-scores.json`, including `build`, `run`, and
`onchain`. RewardKit writes correctness and quality dimensions to
`/logs/verifier/reward-details.json`. Harbor's primary `reward` is `1` when the
Tempo verifier's independent build/run/onchain score passes, while RewardKit
correctness and quality remain diagnostic so pass@K can be computed from a
single binary reward key.
