# Tempo Evals Contribution Guide

This file defines repository-wide rules. Read the relevant suite README before
changing suite tasks or harnesses:

- [Tempo integration](tasks/tempo-v1/README.md)
- [Tempo MCP efficiency](tasks/tempo-mcp-v1/README.md)
- [MPP integration](tasks/mpp/README.md)

## Repository Contract

Tempo Evals measures working integrations, not plausible-looking code. Every
task needs a clear instruction, reproducible environment, independent verifier,
minimal oracle solution, and programmatic Harbor reward. RewardKit quality
checks are diagnostic; they must not replace deterministic correctness checks.

Benchmark majors are immutable contracts: task set, prompt, fixtures, verifier
behavior, and scoring. Make compatible maintenance changes in place. Create a
new major dataset version for changes that make results incomparable.

## Documentation Ownership

| Document | Owns |
| --- | --- |
| Root `README.md` | Global purpose, key concepts, setup, architecture, shared workflows, and the task-authoring walkthrough |
| `AGENTS.md` | Repository-wide authoring, validation, and contribution rules |
| Suite `README.md` | Suite purpose, measurements, harness, runs, and implementation notes |
| Task `README.md` | Concise Harbor Hub overview of that task |
| Task `instruction.md` | Agent-facing task contract; keep it minimal and intentional |

Do not move suite-specific runbooks or harness internals into root documents.
Do not change task instructions as a documentation-only cleanup: they are part
of the evaluation contract.

## Sources of Truth and Generated Files

Task directories are authored source. The access profiles, image references,
and shared MPP synchronization rules live in `config/tasks.yaml`; benchmark
identities live in `config/benchmarks.yaml`. Job configs in `config/generated/`
are compiled from `config/job.yaml.j2`, `config/variants.yaml`,
`config/datasets.yaml`, and `config/benchmarks.yaml`.

Use `npm run sync` after changing shared MPP assets or job-config sources. Do
not hand-edit generated MPP harness copies or generated job configs. A suite
README identifies any additional generated files and its canonical authoring
location.

Agent environments extend `shared/global/docker/agent/Dockerfile`; verifier
environments extend `shared/global/docker/verifier/Dockerfile`. Local runs build
both from the checkout. Daytona runs require both CI-published image refs, built
under the same source tag. Registry publishing is restricted to trusted pushes
to `main`; PR validation uses locally built images.

## Authoring Rules

- Follow established task and verifier patterns before adding abstractions.
- Keep task prompts concise and user-facing. Prefer observable files or logs
  for verifier evidence.
- Use the smallest verifier set that establishes correctness. Do not change
  grader weights without an explicit request.
- Do not commit secrets, `.env` files, key material, job output, caches, or
  logs containing credentials.
- Use checked-in TypeScript with `tsx` for Node-side verifier helpers; do not
  add `.mjs` helpers or large inline JavaScript strings in Python.

Task README requirements differ by suite. Follow the suite guide and retain the
existing Harbor Hub style. In particular, Tempo task READMEs describe the
`viem/tempo` and onchain checks; MPP task READMEs describe user-facing behavior
without exposing verifier internals.

## Validation

Run the narrowest relevant validation while iterating, then run the required
artifact refresh before committing.

```bash
npm run task:lint          # task structure, metadata, and canaries
npm run docs:check         # pinned Tempo documentation bundle
npm run check:generated    # shared assets and job-config freshness
npm run check              # full repository check
```

Use the suite README for suite-specific dataset refresh and oracle validation
commands. Include refreshed dataset manifests and generated artifacts in the
same change; do not discard mechanical updates required by CI.

## Contribution Workflow

Start from a clean worktree. Use `git town` commands when available for routine
branch work. Follow existing code style and test changes in proportion to risk.

Use conventional commit messages: `feat:`, `fix:`, `perf:`, `chore:`, `docs:`,
`test:`, `refactor:`, or `ci:`. Be specific.

Pull requests use this concise structure:

```md
## Motivation

<short context>

## Summary

- <change>

## Key design considerations

- <tradeoff or notable detail>
```

Do not include routine test summaries, internal discussion, or harness details
in pull-request descriptions.
