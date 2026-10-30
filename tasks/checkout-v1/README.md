# Checkout Suite

Planned dataset: `tempo/checkout-bench-v1`. Twenty-two Harbor tasks cover eight
merchants with required shipping and discover/directed prompts, plus a cart
store on two payment methods. The dataset is not published.
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

Every merchant has discover/directed native Harbor tasks:

| Discover task | Directed task | Added instruction |
| --- | --- | --- |
| `stripe-card-discover` | `stripe-card-directed` | Use card to pay. |
| `stripe-link-discover` | `stripe-link-directed` | Use Link to pay. |
| `paypal-discover` | `paypal-directed` | Use PayPal to pay. |
| `mpp-ousd-discover` | `mpp-ousd-directed` | Use MPP to pay. |
| `mpp-card-discover` | `mpp-card-directed` | Use card over MPP to pay. |
| `braintree-card-discover` | `braintree-card-directed` | Use card to pay. |
| `shopify-card-discover` | `shopify-card-directed` | Use card to pay. |
| `x402-usdc-discover` | `x402-usdc-directed` | Use x402 to pay. |

### Prepared MPP tasks

Four additional tasks use compact rail names to keep Harbor task slugs short:
`mppcard-prepared-discover`, `mppcard-prepared-directed`,
`mppousd-prepared-discover`, and `mppousd-prepared-directed`.
They share their cold source's merchant, wallet, oracle and grading. The agent
image additionally installs pinned mppx, viem and tsx under `/opt/mpp-client`
and the prompt points to a generic client usage guide. This measures a prepared
client plus instructions, separately from cold discovery. It does not test
preinstallation alone or an already authenticated browser wallet.

`config/tasks.yaml` lists the source tasks; sync generates all prepared copies
from those sources and `shared/checkout/prepared/`. Metadata and exports record
`mpp_client_profile=prepared` (existing tasks export `cold`). Prepared and cold
results remain separate in quality summaries. Use
`--task-filter '*-prepared-*'` to run the four new tasks with any browser
profile. Existing cold prompts and runtime dependencies remain unchanged.

### Braintree card

The Braintree pair uses Hosted Fields for card entry and an explicitly sandbox
gateway. Set `BRAINTREE_MERCHANT_ID`, `BRAINTREE_PUBLIC_KEY`, and
`BRAINTREE_PRIVATE_KEY` in the ignored checkout env file. The new task's wallet
uses Braintree-compatible Mastercard test details, which also support its
shared Stripe Link enrollment. The merchant keys stay in the trusted sidecar.

The verifier searches sandbox transactions by a unique trial reference, even
when a checkout response was lost, and requires exactly one unrefunded card
sale for USD 12 submitted for settlement, settling or settled. Authorization
alone is insufficient. The reference must match the immutable shipping order;
the common shipping verifier checks the complete requested destination. Every
trial has independent orders and wallet state, so shared merchant credentials
do not serialize concurrent runs.

### x402 USDC

The x402 pair copies the OUSD MPP merchant and changes only the advertised
payment: the same shipping form, `POST /shipping` and per-order `/buy` URL
charge through mppx's `evm.charge` with an x402 challenge for Base Sepolia
USDC (`eip155:84532`). The merchant removes the native MPP challenge, binds
each charge to its shipping order with the route scope, and settles through the
public x402 facilitator (`X402_FACILITATOR_URL`, default
`https://x402.org/facilitator`). The notebook costs 1 USDC, not $12, so one
funding balance supports more concurrent trials; the prompt keeps the common
$12 spending limit. Compare its spend in USDC, not against the $12 merchants.

Set `X402_FUNDING_PRIVATE_KEY` in the ignored checkout env file. Before the
merchant reports healthy it sends exactly 1 USDC from that wallet to the trial's
buyer through the facilitator, which pays gas, so neither wallet needs ETH and
concurrent trials never share a transaction nonce. Payments go to the funding
wallet, and the snapshot returns any USDC left in the buyer after the agent stops,
so the balance recycles. The public facilitator sometimes fails to broadcast
concurrent settlements; funding, recovery and the merchant's settlement retry
those failures, which cannot pay twice because each authorization settles once.
The funding key stays in the trusted merchant sidecar.

The verifier requires exactly one delivery, a successful x402 settlement on
Base Sepolia, and a confirmed settlement transaction with exactly one USDC
transfer: 1 USDC from the trial buyer to the merchant. The common shipping check
then joins the delivery to its order and requires that order's recorded total
to be $1.00: `config/tasks.yaml` sets `order_totals` for the pair, which sync
writes into its expected `order.json`. `buyer_balance_after_agent` records USDC
the buyer still held before recovery.

Every task's wallet lists a `baseSepolia` account controlled by the same key
as its Tempo account, so the inventory does not reveal which merchant accepts
x402. Only the x402 tasks fund it.

### Shopify storefront

The Shopify pair uses a dedicated development store and Shopify's test payment
gateway. This measures a hosted storefront/card-form workflow, not live Shopify
Payments processing. Set `SHOPIFY_SHOP` (the full `*.myshopify.com` domain),
`SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `SHOPIFY_VARIANT_ID` (the GraphQL
variant ID), and `SHOPIFY_STOREFRONT_PASSWORD` in the ignored checkout env file.
Create the app and dev store under the same Shopify organization; install the
app with `read_orders`, `read_products`, and `write_products` for catalog setup.
Select custom distribution so the verifier can read protected test-order data.
Client credentials mint short-lived Admin API tokens in trusted sidecars.

Seed one active, published, non-taxable, physical Tempo Notebook at USD 12,
with SKU `TEMPO-NOTEBOOK`, untracked inventory and free US shipping. Activate
Shopify's test payment gateway. Runtime setup checks the development-store flag,
currency, product configuration and order/address read access. The wallet retains its normal Stripe/Link
card and adds `storefront.password` and `storefront.testCard`; Shopify's test
gateway uses card number `1` for an approved test transaction. The storefront
password is shopper access only; Admin app credentials never reach the agent.

The common shipping form forwards the agent's submitted destination into a
Shopify cart permalink; it never supplies the verifier's expected address.
The browser continues to Shopify's hosted checkout through a cart permalink. Each trial
uses its own wallet/contact email, browser session and cart order references.
The shared catalog is configured once; trials never mutate it or share carts.

The snapshot reads Shopify orders independently, matching trial attributes or
unique contact email. Correctness requires exactly one successful test-gateway
sale/capture and paid, unrefunded order for the correct variant, quantity and
USD 12 total. It verifies the final shipping address returned by Shopify,
including changes made in hosted checkout. Duplicate or refunded purchases,
manual payment statuses, wrong items/addresses and real transactions fail.
The unique contact email also correlates purchases made through the storefront
after its password gate drops cart attributes; those tracking fields are not
an extra agent requirement.
Its retry proxy counts distinct checkout order handoffs, so resuming the same
cart after unlocking the dev store is not another attempt. The snapshot also
retains the raw handoff request count.
Run `--task-filter 'shopify-card-*'` for the pair on any existing browser profile.

The eight discover tasks are the authored sources. `config/tasks.yaml` declares
peer names and method instructions; `npm run sync` generates their standalone
directed task directories. Edit the source task to change a pair's merchant,
wallet setup, oracle, verifier, or scoring. Only the task name, provenance marker,
prompt-condition metadata, and added payment instruction differ within a pair.
Generated task copies are marked as generated in GitHub diffs.

`--task-suite checkout` runs all twenty-two tasks, including oracle runs. Use
`--task-filter '*-discover'` for discover only, `--task-filter '*-directed'`
for directed only, or `--task-filter 'stripe-card-*'` for one merchant pair.
No prompt-mode flag is required. Each task and attempt receives a separate
Harbor environment, merchant instance, and funded wallet, including concurrent
runs.

Native `task.toml` fields record `scenario_id`, `prompt_condition`, and
`required_method`. Preflight reuses the scenario identity for credential checks.
Exports prefer the trial's staged task metadata and keep prompt conditions
separate in task and suite quality summaries. OUSD MPP's method is `tempo_mpp`; card MPP's method is `stripe_mpp`; x402's method is `x402`.

`observed_method` comes from provider or receipt evidence, including failed
checkouts. It is blank when unknown or when multiple methods were observed;
`observed_methods` retains the full set as a JSON array. Observing a method does
not imply success. The existing success-only `payment_method` column remains.
Shared observation and grading code lives in `shared/checkout/tests/` and is
copied into every checkout task by `npm run sync`.

## Cart store

Cart tasks put a payment method's unchanged adapter behind a harder store, to
separate models that pass the single-notebook tasks. The request is two A5
dotted Tempo Notebooks and one Tempo Pen for at most $35, shipped to the usual
address. The store lists notebooks in two sizes (A5 $12, A4 $14) and three page
styles, a pen ($4) and a sticker pack ($3). The form defaults to one A4 lined
notebook and preselects Express shipping ($15); only Standard ($5) keeps the
order within budget, at $33. API clients can `GET /catalog` and `POST /shipping`
with `items`, `shippingOption` and `shipping`; the response includes the total.

| Cart task | Source task | Added instruction |
| --- | --- | --- |
| `stripecard-cart-directed` | `stripe-card-discover` | Use card to pay. |
| `mppousd-cart-directed` | `mpp-ousd-discover` | Use MPP to pay. |

`config/tasks.yaml` lists the sources under `checkout.cart`; sync generates each
cart task from its source and `shared/checkout/cart/`. Only the store module,
order fixture, oracle helper and purchase request differ from the source task,
and they are the same for every payment method. Cart tasks are directed only,
so the method is not a second variable. Their `scenario_id` is their own; the
`source_task` metadata selects the source's credential checks.

Every store records an immutable order with its description and total in USD
cents, and every payment adapter charges that order: the single-notebook store
always records "Tempo Notebook" for 1200. Each payment check requires the
provider payment to match the description and total in `tests/order.json`.
The shared `tests/check.py` then requires the paid order's total and, for the
cart, its exact lines and shipping option. A paid order that differs fails as
`order_mismatch`; details and exports record `order_match` and
`order_mismatched_fields` (`total`, `lines`, `shippingOption`).

## Required shipping

Every checkout task requires the same recipient and full shipping destination.
Shipping is part of the default task, alongside buying one Tempo Notebook for
$12; there are no separate shipping task variants.

The eight discover tasks own their merchant adapters, provider snapshots and
oracles. Shared shipping input, order storage, address fixture and verifier
live in `shared/checkout/shipping/`; `npm run sync` copies these assets into
each task before generating directed peers. The provider-specific
`tests/payment_check.py` verifies payment, and the shared `tests/check.py`
requires the matching shipping destination. Wallet setup, browser profiles,
time limits and efficiency weights are unchanged.

The tasks supply a fixed synthetic address in their prompt. The merchant
shows one common, initially empty shipping form with recipient name, street,
apartment/suite, city, state code, postal code and country code. The apartment
field is optional in the generic store but required by this task's destination.
API clients can submit the same fields as a `shipping` JSON object to
`POST /shipping`; the response returns an order-specific `paymentUrl`. This is
available across all eight merchants. Agents choose their own interaction tools.

Submitted destinations are stored as immutable, trial-local orders. The store
checks input structure, not whether it matches the expected answer. Payment
references use that shipping order ID. Both MPP merchants share one server and
differ only in the advertised method: each binds its challenge to the order with
an explicit per-order scope before proxying the delivery endpoint, and the card
merchant also tags its PaymentIntent with the order ID. A shipping order cannot be changed after
creation; another submission creates a distinct draft. In the form adapters,
merchant-managed shipping is collected before provider checkout; PSP billing
addresses and PayPal's saved addresses do not replace this destination.

Each verifier uses the merchant's independent payment check,
then matches its paid order ID to the trusted merchant shipping record. It
compares every supplied field with the verifier's fixture using case-insensitive,
whitespace-normalized equality. A wrong or omitted apartment, another order's
address, duplicate matching records, an unpaid order or duplicate purchase fails.
The verifier records `shipping_address_match` and
`shipping_mismatched_fields` in details. A paid purchase with incorrect shipping
gets zero reward/correctness/quality; efficiency weights remain unchanged.
These sandbox tasks verify the recorded fulfillment destination, not physical
delivery by a carrier. The unpublished v1 tasks now require shipping; earlier
payment-only results are not comparable with these task digests.

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
`0.35 × turn_score + 0.30 × tool_score + 0.20 × retry_score + 0.15 × time_score`.
There is no success floor. Binary `correctness` and `reward` remain unchanged.
Report a final checkout score as `100 × mean_quality`, including failed trials
at zero, beside success rate and raw metrics. Keep prompt conditions separate
and compare equally weighted, matching task/profile cells.

`turn_score = 10 / (10 + model_turns)`, `tool_score = 15 / (15 + tool_calls)`,
`retry_score = 2 ** -extra_checkout_attempts`, and
`time_score = 60 / (60 + trajectory_duration_sec)`.
Turns count model calls in the Harbor trajectory, excluding copied context.
Tools count every tool call in those agent steps, including Bash/research and
failed calls; batching calls in one turn does not hide their cost. A successful
10-turn, 10-call, 60-second checkout without retries scores 0.63.
Trajectory time spans the first user/agent timestamp through the last one;
Harbor's full agent execution duration is exported separately. Setup and
verification time do not contribute to quality. Targets and weights are shared
across merchants. These unpublished v1 scoring changes make earlier quality
scores incomparable; recompute from complete saved trajectories when comparing.
The exporter includes `total_tool_calls` in checkout trial rows, alongside the
existing `quality`, `mean_quality` and `quality_coverage` fields.

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
from repeated Harbor trials. Provider sandbox payments, Base Sepolia transfers and Tempo testnet
transfers must be identified separately in results.
The exporter leaves `pass_5` blank with fewer than five trials. With at least
five, it reports the fraction of five-trial subsets in which every checkout
passed.

Exports keep `model_turns` as the agent-reported count for every trial.
`efficiency_model_turns` separately records the trajectory count used for
quality scoring. Trajectory turns and duration are collected for both successful
and unsuccessful checkouts, even when retry counts are unknown. Missing
trajectory telemetry stays blank; unsuccessful rewards and quality remain zero.
When no MCP bridge trace exists, checkout exports count `mcp_calls` from native
agent trajectory tool calls. Checkout summary totals stay blank if any trial in
the group lacks that metric, including MCP latency and denial counts.

## Raw metrics and the six-model baseline

Run the suite across all browser profiles with three models per provider:

```sh
npm run bench:production -- --task-suite checkout --profile all \
  --models-config config/models.checkout.yaml --n-attempts 1 \
  --concurrency 2 --agent-concurrency 2 --env-file /path/to/.env.local-checkout \
  --agent-image "$(npm run --silent agent-image:ref)" \
  --verifier-image "$(npm run --silent verifier-image:ref)"
```

The original ten-task baseline had 180 trials. The expanded eighteen-task suite
has 324 trials across three browser profiles and six models. The model configuration pins Claude Code and Codex
versions through native Harbor agent kwargs; existing model configs are unchanged.

Keep each native job directory to recompute quality later. `trials.csv` exposes
binary outcome, model/trajectory turns, total tool calls and counts by tool name,
reported tool errors, model-provider tokens/cache/cost, setup/agent/verifier/wall
time, extra checkout attempts, method, shipping match/mismatches and harness
version. `trajectory_path` links the original timestamped tool trace. Missing
telemetry stays unavailable rather than becoming a zero or a perfect score.

Use `--n-attempts 1 --max-retries 0` to retain one native attempt per cell.
Harbor removes earlier exception-attempt directories when it retries. Rerun
infrastructure failures separately to preserve their evidence and distinguish
them from agent checkout failures.

Harbor's read-only merchant collection hook retries once after a failed snapshot
read. Missing merchant evidence is exported as an ineligible `execution_error`
with quality unavailable; the original Harbor rewards remain preserved.

`checkout_start_count` counts Link and PayPal checkout requests independently
of their reused provider orders; the card merchant counts Stripe sessions.
`credentialed_payment_request_count` is MPP's and x402's raw credential-bearing
request count. These are distinct observations; the current retry score uses
the existing per-rail proxy. Reported tool errors count native error flags and
explicit tool-error envelopes, not every failed action inside a shell command.

`native_total_tool_calls`, `native_tool_calls_by_name`, `native_mcp_calls`, and
`native_failed_tool_calls` preserve executed calls from each CLI's native log.
These include browser calls nested inside Codex's code tool. The existing
`total_tool_calls` and efficiency score continue to count Harbor trajectory
calls, which can be code-tool wrappers. Native failures use explicit error
flags/statuses or nonzero command exits. Keep both counts when comparing agent
harnesses; the timestamped native logs retain the underlying evidence.
Raw trajectories, verifier details and trusted provider snapshots remain the
source of evidence, independent of the weighted quality formula.
If the CLI log is missing, exports can recover Claude calls and recorded cost
from Harbor's archive for the exact trajectory session. The last cost state
determines cost; unknown costs stay blank. Archive tool counts stay blank when
the main transcript delegates to subagents, whose separate transcripts are not
included in this fallback.

## Current merchants

All eight merchant scenarios request one Tempo Notebook for at most $12 and use
the same purchase request and Playwright browser. Each trial wallet lists its
prepared payment methods. Only directed prompts name the method to use. Each
merchant runs in a trusted sidecar and exposes only its own checkout flow.

Harbor starts a separate environment for each task and trial. In that
environment, `http://merchant:3000` resolves to that task's merchant container.
The shared address is local to the trial; agents cannot browse another task's
merchant through it.

| Task | Payment surface | Independent proof |
| --- | --- | --- |
| `stripe-card-discover` | Stripe Checkout card form | One paid card PaymentIntent and matching order |
| `stripe-link-discover` | Link Express Checkout button only | One paid Link PaymentIntent and matching order |
| `mpp-ousd-discover` | MPP OUSD paid endpoint only | One notebook delivery, successful MPP receipt, and exact trial-recipient OUSD balance |
| `mpp-card-discover` | Stripe MPP card paid endpoint only | One notebook delivery and MPP receipt matched to a captured, unrefunded sandbox card PaymentIntent |
| `paypal-discover` | Merchant PayPal checkout button and hosted sandbox buyer approval form | One completed PayPal order and capture |
| `braintree-card-discover` | Braintree Hosted Fields card form | One unrefunded sandbox card sale submitted for settlement and matching shipping order |
| `shopify-card-discover` | Shopify development storefront and test card gateway | One paid, unrefunded test order with matching variant, total, trial and provider-recorded shipping address |
| `x402-usdc-discover` | x402 Base Sepolia USDC paid endpoint only | One notebook delivery, successful x402 settlement and confirmed 1 USDC transfer from the trial buyer |
Every trial runs the same wallet, Link enrollment, and browser services before
the agent starts. After Link enrollment, a shared Compose readiness step opens
the merchant through the selected browser. A broken browser connection fails
environment setup before the agent starts. The wallet service creates a fresh
Tempo testnet payer and confirms its faucet funding independently of other
trials. Link enrollment prepares a unique identity using a synthetic sandbox card. The agent sees the
same base wallet inventory across tasks; merchant and verifier sidecars differ.
Shopify adds shopper access and test-gateway details under `wallet.storefront`,
and Braintree uses a compatible sandbox card fixture. Cold MPP agents receive no preinstalled payment helper or payment
SDK and may install the dependencies they choose. Prepared tasks add the client
and guide described above. Merchant credentials stay in
trusted sidecars.

The common Link setup is authored in `shared/checkout/wallet/link_setup.js`
and copied to every task by sync. It also prepares a unique, one-use Stripe
sandbox shared payment token (SPT), with a $12 USD limit and two-hour expiry,
under `card.sharedPaymentToken` in the wallet inventory. The agent receives the
token and its limits, never the Stripe secret key. This uses Stripe's official
[granted-token test helper](https://docs.stripe.com/agentic-commerce/concepts/shared-payment-tokens)
without an interactive Link CLI authorization. It evaluates paying an MPP
challenge with an already prepared card credential; it does not evaluate
obtaining a credential or purchase approval. The `mpp-card` merchant advertises
only Stripe MPP card payments and independently lists this trial's Stripe
PaymentIntents during verification, including charges without a delivery.

Set `STRIPE_TEST_SECRET_KEY`, `PAYPAL_SANDBOX_BUYER_EMAIL`, and
`PAYPAL_SANDBOX_BUYER_PASSWORD` for every checkout task. Link also requires
`STRIPE_TEST_PUBLISHABLE_KEY`; PayPal also requires
`PAYPAL_SANDBOX_CLIENT_ID` and `PAYPAL_SANDBOX_CLIENT_SECRET`. Independent
Tempo wallets and Link identities need no shared funding pool, so the checkout
runner does not cap trial concurrency.
Before publishing, run each task's oracle on Daytona and one unpaid trial that
scores zero; verify the Link-only page
actually excludes direct card entry. Refresh the dataset manifest and run
repository checks. Browser infrastructure profiles are described below.

Changes to task prompts, fixtures, verification, or scoring after publication
must follow the repository's benchmark-major versioning rule.

## Browser infrastructure profiles

The original design varies browser infrastructure while keeping the browser
tool identical. Checkout supports `--profile local`, `--profile browserbase`,
and `--profile kernel`. Omitting the flag (or using the existing `docs` default)
selects local. `--profile all` launches three ordinary Harbor jobs, selecting
all twenty-two tasks per job. Model trials retain the shared pair
ID. Existing
profile behavior for other suites is unchanged.

For example, run the entire oracle matrix on Daytona:

```sh
npm run bench:daytona:oracle -- --task-suite checkout --profile all \
  --env-file /path/to/.env.local-checkout --concurrency 2 \
  --agent-image "$(npm run --silent agent-image:ref)" \
  --verifier-image "$(npm run --silent verifier-image:ref)"
```

Use the same flags with `bench:daytona:agent:dev` for a single model attempt per
task; `--model` chooses the model. Add `--agent-concurrency` at or below the
trial concurrency. Concurrency is per job, so the three-profile matrix can
start three times that many trials; provider plans must allow those sessions.

Browserbase requires `BROWSERBASE_API_KEY` and `BROWSERBASE_PROJECT_ID`, plus
support for keep-alive sessions. Kernel requires `KERNEL_API_KEY`. Put these in
the ignored local env file alongside the existing payment sandbox credentials.
The matrix checks all required credentials before starting any job.

Profiles are staged at run time using the existing Harbor task-copy pipeline.
No new task directories or runner are added. `shared/checkout/browser/` contains
the common page hook and cloud session sidecar. Every profile extends the same
task-pinned Playwright MCP image and exposes `http://browser:8931/mcp` with the
same tools, US English locale, UTC timezone, and 1280x720 viewport.
Browser output files are shared read-only with the agent at the absolute paths
returned by MCP. PayPal orders also request US English for the hosted checkout.
Page-published WebMCP tools are disabled to keep this infrastructure comparison
on the same fixed browser toolset.
Prompts, funded wallets, merchant implementations, oracles, verifier
and rewards are identical across profiles. Agents can still install tools of
their choice; this comparison does not restrict them to browser use. Checkout
enables Codex's live web search, while Claude Code retains its native research
tools. Both can also fetch documentation and install dependencies through the
terminal. Other suites retain their existing research settings.

Each cloud trial creates its own provider session. Account API keys and the
authenticated upstream CDP URL stay in a trusted Compose sidecar; it relays
only that trial's CDP connection to the browser MCP service. The common page
hook routes `http://merchant:3000` requests through the local MCP process, so
the cloud browser can reach its trial's private merchant without a public
store URL. Hosted Stripe/PayPal traffic runs in the selected browser. This
routing also applies to local, including POST bodies, cookies and redirects.

Cloud sessions are explicitly released when Compose stops, with a 40-minute
sidecar lifetime and provider timeout as fallbacks. Browserbase uses direct
egress with CAPTCHA solving disabled; Kernel uses headless, non-stealth
browsers. Provider Chromium versions and network latency can still differ.
This matrix measures those infrastructure differences through a common tool,
not identical browser binaries.

Staged task metadata records `browser_profile`; the native agent config also
retains `CHECKOUT_BROWSER_PROFILE` so it survives removal of the staged files.
Existing exports group
trials and summaries by `profile` (`local`, `browserbase`, or `kernel`), alongside
the existing prompt-condition fields. Older runs without profile metadata keep
their `browser-mcp` label. Setup time stays separate from agent execution time.
