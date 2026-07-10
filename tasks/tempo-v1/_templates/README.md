# Tempo task templates

Authored templates for the Tempo Harbor tasks. Each `tasks/tempo-v1/_templates/<slug>/`
directory generates one canonical task under `tasks/tempo-v1/`. Benchmark jobs
select the Docs or MCP access profile, so both profiles still receive separate
scores without duplicating task artifacts. `npm run sync` regenerates tracked
output from scratch; never edit generated task directories by hand.

A template task contains only the authored files:

- `instruction.md` — the agent-facing prompt. It must contain exactly one
  `<!-- tempobench_sync -->` placeholder, which sync replaces with the shared
  execution constraints and Docs access block from `config/tasks.yaml`.
- `README.md` — the Harbor Hub display summary. It must include `## Overview`,
  `## What the Task Tests`, and `## Verification`.
- `task.toml` — canonical task config. `[task].name` is the bare intent
  (`tempo-v1/<slug>`); the benchmark job injects the MCP server for the MCP
  profile. Tempo fixture values live in `config/tasks.yaml` under `fixture_env`
  and `case_fixtures`;
  sync renders them into each generated task's `[environment.env]`. Shared
  compose injects those keys into `main` so shared-mode verifier commands
  inherit the same env. Sync rejects duplicated `[verifier.env]` blocks.
- `tests/correctness/criteria.py` — task-specific RewardKit criteria.
- `solution/` — the oracle solution used for sanity checks. A normal minimal
  TypeScript app; `solve.sh` only copies the files into `/app`.

Tempo correctness criteria should require `viem/tempo` `Actions.*` APIs and
reject non-Tempo blockchain SDKs such as Solana, Sui, `ethers`, and `web3`.
Use `Actions.faucet.fundSync` for localnet funding rather than raw faucet RPCs
or hand-written contract calls.

Everything else in a generated task (environment, verifier package, quality
checks, test harness) comes from `shared/` and `config/tasks.yaml`.

To add a task:

1. Create `tasks/tempo-v1/_templates/<slug>/` with the files above.
2. Add the slug to `task_slugs` in `config/tasks.yaml`.
3. Add a verifier case at `shared/tempo/verifier/src/cases/<case>.js` and set
   `TEMPO_BENCH_CASE` for the slug in `config/tasks.yaml` `case_fixtures`.
4. Run `npm run sync`, then `npm run dataset` to refresh digests.
