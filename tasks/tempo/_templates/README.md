# Tempo task templates

Authored templates for the Tempo Harbor tasks. Each `tasks/tempo/_templates/<slug>/`
directory generates three tasks under `tasks/tempo/`: `<slug>-base`,
`<slug>-docs`, and `<slug>-mcp`. `npm run sync` regenerates that output from
scratch; never edit generated profile task directories by hand.

A template task contains only the authored files:

- `instruction.md` — the agent-facing prompt. It must contain exactly one
  `<!-- tempobench_sync -->` placeholder, which sync replaces with the shared
  execution constraints (and the per-profile access block for docs/MCP
  variants) from `config/tasks.yaml`.
- `task.toml` — profile-neutral task config. `[task].name` is the bare
  intent (`tempo/<slug>`); sync appends the profile suffix, description
  label, keywords, per-profile env, and MCP servers. Put Tempo fixture
  values in `[environment.env]`; shared compose injects those keys into
  `main` so shared-mode verifier commands inherit the same env. Sync rejects
  duplicated `[verifier.env]` blocks.
- `tests/correctness/criteria.py` — task-specific RewardKit criteria.
- `solution/` — the oracle solution used for sanity checks. A normal minimal
  TypeScript app; `solve.sh` only copies the files into `/app`.

Everything else in a generated task (environment, verifier package, quality
checks, test harness) comes from `shared/` and `config/tasks.yaml`.

To add a task:

1. Create `tasks/tempo/_templates/<slug>/` with the files above.
2. Add the slug to `task_slugs` in `config/tasks.yaml`.
3. Add a verifier case at `shared/tempo/verifier/src/cases/<case>.js` and set
   `TEMPO_BENCH_CASE` in the source `task.toml`.
4. Run `npm run sync`, then `npm run dataset` to refresh digests.
