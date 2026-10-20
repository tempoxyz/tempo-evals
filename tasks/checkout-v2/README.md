# Checkout Suite

Planned dataset: `tempo/checkout-bench-v2`. The four merchant tasks have passed
Daytona oracle validation but the dataset is not published. They can only be
selected with `--task-suite checkout` and are excluded from the default and
`all` benchmark jobs.

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
tasks/checkout-v2/<merchant-item>/
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

## Current merchants

All four tasks request one Tempo Notebook for at most $12 and use the same
purchase request and Playwright browser. Each trial wallet lists its prepared
payment methods. The method to use is not named in the instruction. Each
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
