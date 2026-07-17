# Contributing to Tempo Evals

Thank you for improving Tempo Evals. This repository measures working
integrations, so every contribution must preserve reproducibility and have
observable verification.

## Before you start

- Use Node.js, Docker, `uv`, and the setup steps in the [README](README.md).
- Discuss new benchmark capabilities or task changes in an issue before doing
  substantial implementation work.
- Do not include credentials, funded private keys, job output, or any
  proprietary data in a pull request.

## Making a change

1. Keep the checkout clean and create a focused branch.
2. Read the applicable suite guide before changing a task:
   [`tasks/tempo-v1`](tasks/tempo-v1/README.md),
   [`tasks/tempo-mcp-v1`](tasks/tempo-mcp-v1/README.md), or
   [`tasks/mpp`](tasks/mpp/README.md).
3. Follow the task contract in [AGENTS.md](AGENTS.md). Task instructions,
   fixtures, verifiers, and scoring form part of a benchmark-major contract;
   incompatible changes require a new major dataset version.
4. Run the narrowest relevant validation while iterating, then run:

   ```bash
   npm run check
   npm run check:generated
   ```

5. Explain the user-visible motivation, the benchmark impact, and the
   validation performed in the pull request.

## Task contributions

Tasks need a concise instruction, reproducible environment, independent
verifier, minimal oracle solution, and deterministic Harbor reward. Use
`npm run task:new -- --suite <suite> --name <task>` to scaffold a task, then
follow its suite guide. Do not hand-edit generated artifacts; run `npm run
sync` after changing their source inputs.

## Code and review expectations

Keep changes small, follow existing patterns, and include regression coverage
for changed behavior. Maintainers may request a benchmark-major version bump
when a proposed change would invalidate comparisons with existing results.
