# Checkout Suite

Planned dataset: `tempo/checkout-bench-v1`. The first Stripe merchant task is
under development. It can only be selected with `--task-suite checkout` and is
excluded from the default and `all` benchmark jobs. The browser oracle and
independent provider verifier have passed one paid Stripe sandbox run on Daytona.

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
The exporter leaves `pass_5` blank with fewer than five trials. With at least
five, it reports the fraction of five-trial subsets in which every checkout
passed.

## Bringing the First Merchant Online

The `stripe-notebook` task uses a Stripe sandbox secret in the merchant sidecar,
a per-trial funded Tempo testnet payer in a read-only agent wallet volume, a
sandbox card, a prepared Link sandbox identity, and a Playwright MCP browser.
Set `STRIPE_TEST_SECRET_KEY` and `CHECKOUT_LINK_TEST_EMAIL` in the runner's
secret environment. Never commit either value. The merchant key is interpolated
only into the merchant sidecar; it is not included in the agent wallet.
The Link identity must already have a sandbox funding source; this task does
not yet provision a fresh Link account for each trial. Keep scored runs off
until that isolation is proven.

The checkout runner route and EvalKit validation are opt-in. Before publishing
this task, prove one paid Stripe sandbox purchase through the browser oracle on
Daytona and one unpaid run that scores zero. Then establish a fresh funded Link
identity per trial, refresh the dataset manifest, and run the repository
checks. Add further browser and tool profiles after this first task is proven.

Changes to task prompts, fixtures, verification, or scoring after publication
must follow the repository's benchmark-major versioning rule.
