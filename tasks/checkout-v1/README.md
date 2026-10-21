# Checkout Suite

Planned dataset: `tempo/checkout-bench-v1`. Eight Harbor tasks cover four
merchants with discover and directed prompts. The dataset is not published.
Checkout tasks can only be
selected with `--task-suite checkout` and are excluded from the default and
`all` benchmark jobs.

## What It Measures

An agent receives a request to buy a specific item from a test merchant. The
instruction lists the payment capabilities available in the same benchmark
wallet inventory for every task. By default it does not prescribe a method or
disclose which methods the merchant accepts. The agent chooses a route and
completes the purchase without a trial reset or human intervention.

The merchant and item define a Harbor task. Browser and tool configurations,
agent/model pairs, and independent attempts belong in job configurations rather
than duplicated task directories. The payment method used is observed
independently of the prompt condition.

## Payment prompt pairs

Every merchant has two native Harbor tasks in the same dataset:

| Discover task | Directed task | Added instruction |
| --- | --- | --- |
| `stripe-card-checkout` | `stripe-card-directed` | Use card to pay. |
| `stripe-link-checkout` | `stripe-link-directed` | Use Link to pay. |
| `paypal-checkout` | `paypal-directed` | Use PayPal to pay. |
| `mpp-ousd-checkout` | `mpp-ousd-directed` | Use MPP to pay. |

The original four tasks are the authored sources. `config/tasks.yaml` declares
peer names and method instructions; `npm run sync` generates their standalone
directed task directories. Edit the source task to change a pair's merchant,
wallet setup, oracle, verifier, or scoring. Only the task name, provenance marker,
prompt-condition metadata, and added payment instruction differ within a pair.
Generated task copies are marked as generated in GitHub diffs.

`--task-suite checkout` runs all eight tasks, including oracle runs. Use
`--task-filter '*-checkout'` for discover only, `--task-filter '*-directed'`
for directed only, or `--task-filter 'stripe-card-*'` for one merchant pair.
No prompt-mode flag is required. Each task and attempt receives a separate
Harbor environment, merchant instance, and funded wallet, including concurrent
runs.

Native `task.toml` fields record `scenario_id`, `prompt_condition`, and
`required_method`. Preflight reuses the scenario identity for credential checks.
Exports prefer the trial's staged task metadata and keep prompt conditions
separate in task and suite quality summaries. MPP's method is `tempo_mpp`.

`observed_method` comes from provider or receipt evidence, including failed
checkouts. It is blank when unknown or when multiple methods were observed;
`observed_methods` retains the full set as a JSON array. Observing a method does
not imply success. The existing success-only `payment_method` column remains.
Shared observation and grading code lives in `shared/checkout/tests/` and is
copied into every checkout task by `npm run sync`.

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

Like the MPP integration suite, publish native Harbor `correctness`, `quality`,
and `reward` fields. The merchant verifier determines binary `correctness` and
`reward`. A failed checkout gets zero for all three. After a verified payment,
RewardKit combines deterministic efficiency criteria into `quality`:
`0.6 + 0.4 × (0.40 × turn_score + 0.35 × retry_score + 0.25 × time_score)`.
The existing exporter reports `quality`, `mean_quality`, and `quality_coverage`;
it does not compute a separate checkout score.

`turn_score = min(1, 10 / model_turns)`, `retry_score = 1 / (1 +
extra_checkout_attempts)`, and `time_score = min(1, 180 / trajectory_duration_sec)`.
Turns count model calls in the Harbor trajectory, excluding copied context.
Trajectory time spans the first user/agent timestamp through the last one;
Harbor's full agent execution duration is exported separately. Setup and
verification time do not contribute to quality. The fixed targets are shared
across merchants and should be calibrated before dataset publication.

Stripe and PayPal count extra checkout starts. MPP counts requests carrying
payment credentials beyond the first one; unpaid discovery and 402 challenges
are not retries. These are observable proxies for retries, not counts of every
failed payment submission. Missing trajectory data or attempt counts leave a
successful trial's quality absent. Oracle purchases still receive `reward = 1`.
Checkout quality aggregates are left blank unless every trial in the group has
quality, so missing successful telemetry cannot bias averages toward failures.

The shared grader and RewardKit criteria are authored in
`shared/checkout/tests/` and copied into each task by `npm run sync`. Merchant
correctness checks remain task-owned. Report `pass@1`, all-five-pass
reliability (`pass^5`), tokens, turns, tool calls, wall time, and provider cost
from repeated Harbor trials. Provider sandbox payments and Tempo testnet
transfers must be identified separately in results.
The exporter leaves `pass_5` blank with fewer than five trials. With at least
five, it reports the fraction of five-trial subsets in which every checkout
passed.

## Current merchants

All four merchant scenarios request one Tempo Notebook for at most $12 and use
the same purchase request and Playwright browser. Each trial wallet lists its
prepared payment methods. Only directed prompts name the method to use. Each
merchant runs in a trusted sidecar and exposes only its own checkout flow.

Harbor starts a separate environment for each task and trial. In that
environment, `http://merchant:3000` resolves to that task's merchant container.
The shared address is local to the trial; agents cannot browse another task's
merchant through it.

| Task | Payment surface | Independent proof |
| --- | --- | --- |
| `stripe-card-checkout` | Stripe Checkout card form | One paid card PaymentIntent and matching order |
| `stripe-link-checkout` | Link Express Checkout button only | One paid Link PaymentIntent and matching order |
| `mpp-ousd-checkout` | MPP OUSD paid endpoint only | One notebook delivery, successful MPP receipt, and exact trial-recipient OUSD balance |
| `paypal-checkout` | Merchant PayPal checkout button and hosted sandbox buyer approval form | One completed PayPal order and capture |
Every trial runs the same wallet, Link enrollment, and browser services before
the agent starts. The wallet service creates a fresh Tempo testnet payer and
confirms its faucet funding independently of other trials. Link enrollment
prepares a unique identity using a synthetic sandbox card. The agent sees the
same wallet fields and payment methods across tasks; merchant and verifier
sidecars differ. MPP agents receive no preinstalled payment helper or payment
SDK and may install the dependencies they choose. Merchant credentials stay in
trusted sidecars.

Set `STRIPE_TEST_SECRET_KEY`, `PAYPAL_SANDBOX_BUYER_EMAIL`, and
`PAYPAL_SANDBOX_BUYER_PASSWORD` for every checkout task. Link also requires
`STRIPE_TEST_PUBLISHABLE_KEY`; PayPal also requires
`PAYPAL_SANDBOX_CLIENT_ID` and `PAYPAL_SANDBOX_CLIENT_SECRET`. Independent
Tempo wallets and Link identities need no shared funding pool, so the checkout
runner does not cap trial concurrency.
Before publishing, run each task's oracle on Daytona and one unpaid trial that
scores zero; verify the Link-only page
actually excludes direct card entry. Refresh the dataset manifest and run
repository checks. Add browser and tool profiles after these merchant flows
are validated.

Changes to task prompts, fixtures, verification, or scoring after publication
must follow the repository's benchmark-major versioning rule.
