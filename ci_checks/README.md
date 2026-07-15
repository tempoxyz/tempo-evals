# Static Checks

This directory ports the static task checks from
[harbor-framework/benchmark-template](https://github.com/harbor-framework/benchmark-template/blob/main/.github/workflows/static-checks.yml)
(upstream commit `d3b1e33bf14c8be526f096b2acd8f22a10352b3a`).

The checks are run by [`.github/workflows/static-checks.yml`](../.github/workflows/static-checks.yml)
for each changed `tasks/<suite>/<task>` directory. Run a check locally from the
repository root with:

```bash
bash ci_checks/check-task-timeout.sh tasks/tempo-v1/set-fee-token
```

The workflow's committed `STATIC_CHECKS_MODE` setting controls enforcement:
`warning` reports violations without failing the job, while `error` makes them
blocking. Tempo Bench uses `error` mode after aligning the ported checks with
its task contracts.
