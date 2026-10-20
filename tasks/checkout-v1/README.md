# Checkout Suite

Planned dataset: `tempo/checkout-bench-v1`. The five merchant tasks have passed
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

## Current merchants

All five tasks request one Tempo Notebook for at most $12 and use the same
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
| `x402-usdc-checkout` | x402 Base Sepolia USDC endpoint only | One delivered order and matching settled 12 USDC transfer |

The wallet setup creates a fresh funded Tempo testnet payer and Link identity
for each trial. The sandbox card is synthetic. PayPal sandbox buyer credentials
are supplied by the runner; provision distinct buyers for concurrent PayPal
trials. The x402 task funds a fresh Base Sepolia buyer from a testnet funding
pool. Its merchant recipient is that pool, so successful payments replenish it.
MPP and x402 agents receive no preinstalled payment helper or payment SDK; they
may consult public documentation and install the dependencies they choose.
After the agent stops, a trusted recovery sidecar returns unspent buyer USDC.
The runner serializes x402 trials so the shared pool has only one pending funding
transfer. The pool key stays in the trusted payment and recovery sidecars; the
agent sees only its trial wallet. Merchant secrets remain in trusted sidecars.

Set `STRIPE_TEST_SECRET_KEY` for Stripe card and Link tasks and
`STRIPE_TEST_PUBLISHABLE_KEY` for Link. Set
`PAYPAL_SANDBOX_CLIENT_ID`, `PAYPAL_SANDBOX_CLIENT_SECRET`,
`PAYPAL_SANDBOX_BUYER_EMAIL`, and `PAYPAL_SANDBOX_BUYER_PASSWORD` for the PayPal
task. Set `X402_FUNDING_PRIVATE_KEY` and the corresponding public
`X402_RECIPIENT_ADDRESS` for the x402 task. The pool needs at least 12 Base
Sepolia test USDC and a little test ETH for funding and recovery transfers.
Before publishing, run each task's oracle on Daytona and one unpaid trial that
scores zero; verify the Link-only page
actually excludes direct card entry. Refresh the dataset manifest and run
repository checks. Add browser and tool profiles after these merchant flows
are validated.

Changes to task prompts, fixtures, verification, or scoring after publication
must follow the repository's benchmark-major versioning rule.
