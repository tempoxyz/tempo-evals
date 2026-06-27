# Tempo Bench

Minimal Harbor-based benchmark for measuring whether Tempo docs and agent tools
help agents build real Tempo integrations.

The current V0 has two tasks for the same integration:

- `tempo/transfer-with-memo`: baseline task with the prompt and fixture env.
- `tempo/transfer-with-memo-docs-mcp`: same task with a Tempo docs MCP sidecar.

Both ask for a TypeScript script that sends a TIP-20 `transferWithMemo` on a
Tempo localnet. The verifier independently builds and runs the submission, then
checks localnet for the expected onchain event.

## Layout

```text
.
├── job.yaml
├── scripts/
│   └── sync-shared.mjs
├── shared/
│   ├── docker/
│   │   └── tempo-localnet/
│   ├── mcp/
│   │   └── tempo-docs/
│   └── verifier/
│       ├── bin/tempo-bench-verify.js
│       └── src/
└── tasks/
    ├── dataset.toml
    ├── README.md
    ├── transfer-with-memo/
    └── transfer-with-memo-docs-mcp/
        ├── instruction.md
        ├── task.toml
        ├── environment/
        ├── solution/
        └── tests/
```

`shared/` is the source of truth for reusable code. Harbor tasks still need to
be self-contained, so `scripts/sync-shared.mjs` vendors shared pieces into each
task before running or refreshing the dataset manifest.

## Harbor Concepts

- `job.yaml` is the Harbor job. It selects the local Docker orchestrator, the
  `oracle` sanity-check agent, and the `tasks/` dataset.
- `tasks/dataset.toml` is the Harbor dataset manifest for the future
  `tempo/tempo-bench` benchmark.
- `tasks/*/task.toml` is the task config. This is the main place to change
  fixture values, verifier case, timeouts, MCP servers, and environment
  resources.
- `tasks/*/instruction.md` is the agent-facing prompt.
- `tasks/*/environment/docker-compose.yaml` adds task sidecars. Both tasks add a
  localnet sidecar. Harbor owns the `main` service and merges this file into its
  base Compose config.
- `tasks/transfer-with-memo-docs-mcp` also declares a `tempo-docs` MCP server in
  `task.toml` and runs it as the `tempo-docs-mcp` Compose sidecar.
- `tasks/*/tests/test.sh` is Harbor's verifier entrypoint. It installs the
  vendored verifier package and writes `/logs/verifier/reward.json`.
- `tasks/*/solution/solve.sh` is used only by Harbor's `oracle` agent for sanity
  checks.

## Configuration

The task TOML has two Harbor-native env maps:

- `[environment.env]` is injected into the agent/submission container.
- `[verifier.env]` is injected into Harbor's verifier process.

For this benchmark, both maps carry the same Tempo fixture:

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
The verifier reads the same values from `[verifier.env]`, records the starting
block, runs the submission, and verifies the onchain event independently of
anything the submission writes.

Run `node scripts/sync-shared.mjs` after changing task config. The sync script
also checks that Tempo fixture keys in `[environment.env]` and `[verifier.env]`
match, because Harbor keeps those phase env maps separate.

## Development Loop

Install Harbor:

```bash
uv tool install harbor
```

Sync shared code into tasks:

```bash
node scripts/sync-shared.mjs
```

Refresh task digests in the dataset:

```bash
harbor sync tasks
```

Run the oracle solution:

```bash
harbor run -c job.yaml -y
```

Open Harbor's viewer:

```bash
harbor view jobs
```

## Adding Pieces

Add a task:

1. Copy `tasks/transfer-with-memo` to a new task directory.
2. Update `task.toml` name, metadata, fixture env, and `TEMPO_BENCH_CASE`.
3. Update `instruction.md`.
4. Run `node scripts/sync-shared.mjs`.
5. Run `harbor add ./tasks/<task-dir> --to tasks`.

Add a verifier:

1. Add a case file under `shared/verifier/src/cases/`.
2. Export it from `shared/verifier/src/cases/index.js`.
3. Set `TEMPO_BENCH_CASE` in the task TOML.
4. Run `node scripts/sync-shared.mjs`.

Add an MCP profile:

1. Add the MCP server under `shared/mcp/` if it is reusable.
2. Add the MCP server as a sidecar in the task's `environment/docker-compose.yaml`.
3. Declare it in `task.toml` using Harbor's `[[environment.mcp_servers]]`.
4. Keep the fixture and verifier unchanged unless the actual task changes.
5. Run `node scripts/sync-shared.mjs`.

Add a metric:

1. Compute it in `shared/verifier/src/index.js` or the relevant case verifier.
2. Include it in `/logs/verifier/reward.json`.
3. Keep `reward` as the primary Harbor score.

## Score

The verifier writes:

```json
{
  "reward": 1,
  "build": 1,
  "run": 1,
  "onchain": 1
}
```

`reward` is `1` only when the submission builds, runs, and the verifier observes
the expected `TransferWithMemo` event on Tempo localnet.
