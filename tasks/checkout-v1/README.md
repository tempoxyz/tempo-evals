# Checkout Suite (Scaffolding)

Planned dataset: `tempo/checkout-bench-v1`. No tasks are published yet. The
suite is not included in benchmark jobs until a merchant task has an oracle and
independent verifier.

## What It Measures

An agent receives a request to buy a specific item from a test merchant. The
instruction lists the payment capabilities available in the same benchmark
wallet inventory for every task, but does not prescribe a method or disclose
which methods the merchant accepts. The agent chooses a route and completes the
purchase without a trial reset or human intervention.

The merchant and item define a Harbor task. Browser and tool configurations,
agent/model pairs, and independent attempts belong in job configurations rather
than duplicated task directories. The payment method used is an observed result,
not an assigned task variant.

## Task Contract

Scaffold a merchant task with:

```sh
npm run task:new -- --suite checkout --name merchant-item
```

The generated files are placeholders and are not runnable until completed:

```text
tasks/checkout-v1/<merchant-item>/
├── README.md               # Harbor Hub overview
├── instruction.md          # Item, merchant, spending limit, wallet inventory
├── task.toml               # Task resources and declared artifacts
├── environment/            # Agent image and merchant/browser sidecars
├── solution/solve.sh       # Oracle purchase, never shown to the agent
└── tests/                  # Independent, separate-environment verifier
```

Use Harbor's multi-container environment for a controlled merchant and local
browser where needed. Keep merchant payment credentials and expected answers
outside the agent container. Declare any merchant-side evidence as additional
`task.toml` artifacts; the agent trajectory is the required first artifact.
The verifier must confirm the requested item, permitted total, completed order,
and matching provider or chain payment, and reject duplicate orders or charges.
An agent's final message or a success page alone does not establish success.

Publish a binary `reward` for verified checkout success. Record the chosen
payment method and checkout stage as diagnostics. Report `pass@1`, all-five-pass
reliability (`pass^5`), tokens, turns, tool calls, wall time, and provider cost
from repeated Harbor trials. Provider sandbox payments and Tempo testnet
transfers must be identified separately in results.

## Bringing the First Merchant Online

1. Implement the merchant's test checkout and a per-trial credential inventory.
2. Complete the oracle and independent verifier; prove both a passing purchase
   and a plausible-looking purchase that the verifier rejects.
3. Refresh the generated images and dataset manifest with `npm run sync` and
   `npm run dataset -- --tasks tasks/checkout-v1`.
4. Register the now-populated suite in the runner, evalkit, and job matrices.
   Add checkout-specific tool/browser profiles and result export fields there.
5. Run the local oracle, task lint, generated-artifact checks, and repository
   checks before publishing the dataset.

Changes to task prompts, fixtures, verification, or scoring after publication
must follow the repository's benchmark-major versioning rule.
