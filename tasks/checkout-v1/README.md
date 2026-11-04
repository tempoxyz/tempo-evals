# Checkout Suite

Planned dataset: `tempo/checkout-bench-v1` (not published). Thirty-six Harbor
tasks cover nine payment methods. Each method has a single-notebook store and a
cart store, and each store has a discover and a directed prompt. Every task
requires shipping. Select them only with `--task-suite checkout`; the default and
`all` jobs exclude them.

## Task matrix

| Method (`required_method`) | Notebook discover | Notebook directed | Cart discover | Cart directed | Directed instruction |
| --- | --- | --- | --- | --- | --- |
| Stripe card (`card`) | `stripe-card-discover` | `stripe-card-directed` | `stripecard-cart-discover` | `stripecard-cart-directed` | Use card to pay. |
| Stripe Link (`link`) | `stripe-link-discover` | `stripe-link-directed` | `link-cart-discover` | `link-cart-directed` | Use Link to pay. |
| PayPal (`paypal`) | `paypal-discover` | `paypal-directed` | `paypal-cart-discover` | `paypal-cart-directed` | Use PayPal to pay. |
| Braintree card (`card`) | `braintree-card-discover` | `braintree-card-directed` | `braintree-cart-discover` | `braintree-cart-directed` | Use card to pay. |
| Shopify card (`card`) | `shopify-card-discover` | `shopify-card-directed` | `shopify-cart-discover` | `shopify-cart-directed` | Use card to pay. |
| MPP OUSD (`tempo_mpp`) | `mpp-ousd-discover` | `mpp-ousd-directed` | `mppousd-cart-discover` | `mppousd-cart-directed` | Use MPP to pay. |
| MPP card (`stripe_mpp`) | `mpp-card-discover` | `mpp-card-directed` | `mppcard-cart-discover` | `mppcard-cart-directed` | Use card over MPP to pay. |
| x402 USDC (`x402`) | `x402-usdc-discover` | `x402-usdc-directed` | `x402-cart-discover` | `x402-cart-directed` | Use x402 to pay. |
| OUSD form (`tempo_transfer`) | `ousd-form-discover` | `ousd-form-directed` | `ousdform-cart-discover` | `ousdform-cart-directed` | Use OUSD to pay. |

Every task runs on three browser profiles (`local`, `browserbase`, `kernel`),
so one attempt per model is 108 trials.

## What it measures

An agent must buy specific items from a test merchant within a budget, ship them
to a given address, and finish without a trial reset or human intervention.
Discover prompts never name a method or say which methods the merchant accepts;
directed prompts add only the sentence in the table. The method actually used is
observed independently of the prompt.

A task is a merchant and its items. Browser profiles, agent/model pairs and
attempts belong in job configurations, not duplicated task directories.

## Agent environment

Harbor gives every task and attempt its own environment, merchant instance and
funded wallet, including concurrent runs. In it, `http://merchant:3000` resolves
to that trial's merchant, a trusted sidecar exposing only its own checkout flow;
agents cannot reach another trial's merchant. Merchant credentials and expected
answers never enter the agent container.

**Prompt.** Apart from the purchase request and the directed sentence, every
prompt is identical: the budget, the shipping address, "Your wallet and tools
are in `/opt/agent`. You have a browser available for checkout.", the wallet's
Link email as the order contact, permission to consult public documentation and
install software, and the 900-second limit.

**Tool bundle.** `/opt/agent` has the same contents in every task: the trial
wallet at `wallet/wallet.json` (the wallet volume, mounted read-only), pinned
mppx, viem and tsx, and a README listing both, how to run scripts there, and a
short working example for each scripted payment: an MPP challenge paid from the
Tempo account or with the prepared card token, an x402 challenge paid from the
Base Sepolia account, and a direct Tempo stablecoin transfer. The examples cover
every scripted rail, so they do not say which one a store accepts; card, Link
and PayPal remain browser forms. Bundle, wallet fields and prompt match across rails, so
in a discover task only the merchant tells the agent which method it accepts,
with one exception: Braintree wallets carry a Mastercard test number
(`5555555555554444`) where every other wallet has `4242424242424242`. Agents
may install other software. No authenticated browser wallet is provided.

**Setup.** Every trial runs the same wallet, Link enrollment and browser
services before the agent starts:

- The wallet service creates a fresh Tempo testnet payer and confirms its faucet
  funding. The same key controls a `baseSepolia` account, listed in every wallet
  and funded only by x402 tasks.
- Every wallet lists a sandbox card, Link, a PayPal sandbox buyer and Shopify
  storefront access (`storefront.password`, `storefront.testCard`). Braintree
  tasks swap in a Braintree-compatible Mastercard test card, which also supports
  Link enrollment; that card number is the only wallet field that differs.
- Link enrollment (`shared/checkout/wallet/link_setup.js`) creates a unique
  identity with a synthetic sandbox card and a unique, one-use Stripe sandbox
  shared payment token (SPT) under `card.sharedPaymentToken`, expiring in two
  hours, limited to $12, or $35 in cart tasks (`card.sharedPaymentTokenMaxAmount`,
  set through the Link service's `SPT_MAX_AMOUNT`). It uses Stripe's
  [granted-token test helper](https://docs.stripe.com/agentic-commerce/concepts/shared-payment-tokens)
  without interactive Link CLI authorization, so it evaluates paying with a
  prepared credential, not obtaining one or purchase approval. The agent never
  receives the Stripe secret key.
- A shared Compose readiness step then opens the merchant through the selected
  browser; a broken browser connection fails setup before the agent starts.

Checkout enables Codex's live web search; Claude Code keeps its native research
tools. Both can fetch documentation and install dependencies through the
terminal. Other suites keep their own research settings.

## Stores

Both stores show one common, initially empty shipping form: recipient name,
street, apartment/suite, city, state code, postal code and country code. API
clients can instead `POST /shipping` with a `shipping` object; the response
returns an order-specific `paymentUrl`. Agents choose their own tools.

**Notebook store.** One Tempo Notebook for at most $12; the order records "Tempo
Notebook" for 1200 cents (100 for x402).

**Cart store.** A harder store that separates models passing the notebook tasks.
The request is two A5 dotted Tempo Notebooks and one Tempo Pen for at most $35,
shipped to the same address. The catalog lists notebooks in two sizes (A5 $12,
A4 $14) and three page styles, a pen ($4) and a sticker pack ($3). The form
defaults to one A4 lined notebook and preselects Express shipping ($15); only
Standard ($5) keeps the order within budget, at $33. API clients can
`GET /catalog` and `POST /shipping` with `items`, `shippingOption` and
`shipping`; the response includes the total. A cart task keeps its source's
unchanged payment adapter; only the store module, order fixture, oracle helper
and purchase request differ, identically for every method. A cart discover trial
measures route choice against a store that accepts only its source's method.

**Orders.** The prompt supplies a fixed synthetic address; the apartment is
optional in the form but required by the destination. Each submission creates
an immutable, trial-local order with its description, total in USD cents and
destination (cart orders add lines and shipping option); resubmitting creates a
new draft. The store
checks structure, not correctness. Every payment adapter charges that order and
references its ID. Form adapters collect shipping before provider checkout, and
PSP billing or PayPal saved addresses never replace it. Both MPP merchants share
one server and differ only in the advertised method; each binds its challenge to
the order with an explicit per-order scope before proxying delivery, and the card
merchant also tags its PaymentIntent with the order ID. Once an order is paid, its
payment URL (MPP and x402 alike) returns the stored order and payment receipt
instead of a new challenge, the way a store's order page confirms a purchase, so
checking a paid order neither looks unpaid nor charges again.

## Merchants

| Merchant | Payment surface | Independent proof |
| --- | --- | --- |
| Stripe card | Stripe Checkout card form | One paid card PaymentIntent and matching order |
| Stripe Link | Link Express Checkout button only | One paid Link PaymentIntent and matching order |
| PayPal | Merchant PayPal button and hosted sandbox buyer approval form | One completed PayPal order and capture |
| Braintree card | Braintree Hosted Fields card form | One unrefunded sandbox card sale submitted for settlement, matching the shipping order |
| Shopify card | Shopify development storefront and test card gateway | One paid, unrefunded test order with matching variant, total, trial and Shopify-recorded address |
| MPP OUSD | MPP OUSD paid endpoint only | One delivery, a successful MPP receipt and the exact trial-recipient OUSD balance |
| MPP card | Stripe MPP card paid endpoint only | One delivery and MPP receipt matched to a captured, unrefunded sandbox card PaymentIntent |
| x402 USDC | x402 Base Sepolia USDC paid endpoint only | One delivery, a successful x402 settlement and a confirmed 1 USDC transfer from the trial buyer |
| OUSD form | Hosted checkout page with an order-specific Tempo deposit address and a confirm button | One confirmed order and exactly its total in OUSD at that order's deposit address, with no other deposits |

**PayPal.** Orders request US English for the hosted checkout.

**MPP card.** The merchant advertises only Stripe MPP card payments.
Verification independently lists the trial's Stripe PaymentIntents, including
charges without a delivery.

**Braintree.** Uses an explicitly sandbox gateway; merchant keys stay in the
sidecar. The verifier searches sandbox transactions by a unique trial reference,
even when a checkout response was lost, and requires exactly one unrefunded card
sale for USD 12 that is submitted for settlement, settling or settled;
authorization alone fails. The reference must match the shipping order. Trials
have independent orders and wallet state, so shared merchant credentials do not
serialize concurrent runs.

**Shopify.** A dedicated development store with Shopify's test gateway: this
measures a hosted storefront and card form, not live Shopify Payments. One-time
setup:

- Create the app and dev store in the same Shopify organization. Install the app
  with `read_orders`, `read_products` and `write_products`, and select custom
  distribution so the verifier can read protected test orders. Client credentials
  mint short-lived Admin API tokens in trusted sidecars; they never reach the
  agent, and the storefront password is shopper access only.
- Seed one active, published, non-taxable, physical Tempo Notebook at USD 12
  (SKU `TEMPO-NOTEBOOK`, untracked inventory, free US shipping) and activate the
  test gateway, which approves card number `1`. Runtime setup checks the
  development-store flag, currency, product configuration and order/address read
  access.
- For the cart, publish the cart catalog at the store's prices with SKUs
  `TEMPO-NOTEBOOK-<SIZE>-<PAGES>`, `TEMPO-PEN` and `TEMPO-STICKERS`, collected as
  "Cart items". The United States market charges Standard $5 for cart items
  (free for the single notebook) and Express $15.

The merchant forwards the agent's submitted destination and lines into a Shopify
cart permalink (never the verifier's address), and the browser continues to
Shopify's hosted checkout. Each trial uses its own contact email, browser
session and cart references; the shared catalog is never mutated or shared
between carts. Shopify preselects the cheapest shipping rate, so the cart's
Express trap applies only to the other methods. The snapshot reads orders
independently, matching trial attributes or the unique contact email (which also
catches purchases after the password gate drops cart attributes; neither is an
agent requirement). It requires exactly one successful test-gateway sale or
capture and a paid, unrefunded order with the right variant(s), quantities,
shipping option and total, at the final address Shopify recorded, including
edits in hosted checkout. Duplicate, refunded, manual-payment, wrong-item,
wrong-address and real transactions fail. The retry proxy counts distinct
checkout handoffs, so resuming a cart after unlocking the store is not a retry;
the raw handoff request count is kept too.

**OUSD form.** The stablecoin counterpart of the card forms, built on the MPP
OUSD merchant with the same shipping form and `POST /shipping`. Instead of a 402
challenge, the order's payment page (`/pay`) is an HTML checkout showing the
total, the OUSD token, Tempo testnet and a fresh deposit address for that order.
The buyer sends the transfer from their wallet and presses Confirm payment
(`POST /pay/confirm`); the store checks the deposit balance onchain and records
the order once it holds the total. A transfer that is never confirmed is money
spent without an order. The verifier reads every issued deposit address and
requires exactly the total at the paid order's address and nothing anywhere
else. Retries count Confirm payment requests beyond the first; overlapping confirms
for one order are handled one at a time, so an order is recorded once. It
measures the same wallet and token as MPP OUSD, paid through a form instead of a
protocol.

**x402.** Copies the MPP OUSD merchant and changes only the advertised payment:
the same shipping form, `POST /shipping` and per-order `/buy` URL charge through
mppx's `evm.charge` with an x402 challenge for Base Sepolia USDC
(`eip155:84532`). The native MPP challenge is removed; each charge is bound to
its order by the route scope and settled through the public facilitator
(`X402_FACILITATOR_URL`, default `https://x402.org/facilitator`). Every x402
order settles for exactly 1 USDC: the notebook store shows $1.00, while the cart
shows its usual $33 and its 402 challenge asks for 1 USDC. Prompts keep the
common spending limits. Compare x402 spend in USDC, not against other merchants.

Before reporting healthy, the merchant sends 1 USDC from the funding wallet
(`X402_FUNDING_PRIVATE_KEY`, kept in the sidecar) to the trial buyer through the
facilitator, which pays gas, so neither wallet needs ETH and trials never share
a nonce; each trial reserves 1 USDC. Payments return to the funding wallet, and
the snapshot recovers any USDC left with the buyer
(`buyer_balance_after_agent` records it first). Funding, recovery and settlement
retry the facilitator's occasional failed concurrent broadcasts, which cannot pay
twice because each authorization settles once. The verifier requires exactly one
delivery, a successful settlement and a confirmed transaction with exactly one
USDC transfer of 1 USDC from the buyer to the merchant. The order total stays
$1.00 for the notebook (`checkout.order_totals` in `config/tasks.yaml`) and $33
for the cart.

## Verification and scoring

Each task's `tests/payment_check.py` verifies the provider or chain payment and
requires it to match the order description and total in `tests/order.json`
(1 USDC for x402). The shared `tests/check.py` then joins the paid order ID to
the trusted shipping record and requires:

- the order's total and, for the cart, its exact lines and shipping option; a
  mismatch fails as `order_mismatch` (`order_match`, `order_mismatched_fields`:
  `total`, `lines`, `shippingOption`);
- every address field equal to the fixture, case-insensitive and
  whitespace-normalized (`shipping_address_match`,
  `shipping_mismatched_fields`). A wrong or omitted apartment, another order's
  address, duplicate matching records, an unpaid order or a duplicate purchase
  fails.

This verifies the recorded fulfillment destination, not carrier delivery. An
agent's final message or a success page alone never counts.

Tasks publish native Harbor `correctness`, `quality` and `reward`. The verifier
sets binary `correctness` and `reward`; a failed checkout scores zero on all
three, and oracle purchases get `reward = 1`. After a verified payment, RewardKit
computes:

```text
quality = 0.35 × turn_score + 0.30 × tool_score + 0.20 × retry_score + 0.15 × time_score
turn_score  = 10 / (10 + model_turns)
tool_score  = 15 / (15 + tool_calls)
retry_score = 2 ** -extra_checkout_attempts
time_score  = 60 / (60 + trajectory_duration_sec)
```

There is no success floor; a 10-turn, 10-call, 60-second checkout without retries
scores 0.63. Turns count model calls in the Harbor trajectory, excluding copied
context. Tool calls count every call in those steps, including Bash, research and
failed calls, however batched. Time spans the first to last user/agent timestamp;
setup and verification are excluded. Weights and targets are shared across
merchants. Extra attempts are per-rail proxies, not counts of every failed
submission: Stripe and PayPal count extra checkout starts, MPP and x402 count
credential-bearing requests beyond the first, and the OUSD form counts Confirm
payment requests beyond the first (unpaid discovery and 402
challenges are not retries). Missing trajectory data or attempt counts leave a
successful trial's quality absent.

Report the checkout score as `100 × mean_quality`, with failed trials at zero,
beside success rate, `pass@1`, `pass^5`, tokens, turns, tool calls, wall time and
provider cost. Keep prompt conditions separate and compare equally weighted,
matching task/profile cells. Report provider sandbox payments, Base Sepolia
transfers and Tempo testnet transfers separately.

## Results and exports

Keep each native job directory to recompute quality later; raw trajectories,
verifier details and provider snapshots remain the evidence. Missing telemetry
stays blank rather than becoming zero or a perfect score.

- `trials.csv`: outcome, model and trajectory turns, `total_tool_calls` and
  counts by tool, reported tool errors (native error flags and tool-error
  envelopes, not every failed shell action), tokens, cache and cost,
  setup/agent/verifier/wall time, extra attempts, method, order and shipping
  match fields, harness version, and `trajectory_path` to the timestamped trace.
  Turns and duration are collected for failed checkouts too.
- `model_turns` is agent-reported; `efficiency_model_turns` is the trajectory
  count used for quality. Harbor's full agent execution time is exported
  separately from trajectory time.
- `checkout_start_count` counts Link and PayPal checkout requests (independent of
  reused provider orders) and Stripe card sessions;
  `credentialed_payment_request_count` is MPP's and x402's raw count.
- `observed_method` comes from provider or receipt evidence, including failed
  checkouts; it is blank when unknown or ambiguous, with the full set in
  `observed_methods`. It does not imply success; `payment_method` is
  success-only.
- `native_total_tool_calls`, `native_tool_calls_by_name`, `native_mcp_calls` and
  `native_failed_tool_calls` come from each CLI's native log and include browser
  calls nested in Codex's code tool; the efficiency score still counts Harbor
  trajectory calls, which can be code-tool wrappers. Keep both when comparing
  harnesses. Without a CLI log, Claude calls and cost come from Harbor's archive
  for the session (last cost state wins); archive tool counts stay blank when
  the transcript delegates to subagents.
- Without an MCP bridge trace, `mcp_calls` counts native trajectory tool calls.
  Summary totals, including MCP latency and denials, stay blank if any trial in
  the group lacks the metric.
- Quality aggregates (`quality`, `mean_quality`, `quality_coverage`) stay blank
  unless every trial in the group has quality. `pass_5` is blank below five
  trials; otherwise it is the fraction of five-trial subsets where every
  checkout passed.
- Exports prefer the trial's staged task metadata and group by `profile`,
  `prompt_condition` and `mpp_client_profile` (`prepared` for every current task).
- The merchant collection hook retries a failed snapshot read once; missing
  evidence exports as an ineligible `execution_error` with quality unavailable,
  keeping Harbor's original rewards.

Results are not comparable across these unpublished v1 changes: required
shipping (earlier runs were payment-only), the current quality formula (recompute
from saved trajectories), and the shared tool bundle (earlier runs exported
`mpp_client_profile=cold`). Runs without profile metadata keep the `browser-mcp`
label.

## Running

Put credentials in an ignored env file; the runner checks every required one
before starting any job.

| Needed for | Variables |
| --- | --- |
| Every task | `STRIPE_TEST_SECRET_KEY`, `PAYPAL_SANDBOX_BUYER_EMAIL`, `PAYPAL_SANDBOX_BUYER_PASSWORD`, `SHOPIFY_STOREFRONT_PASSWORD` |
| Link | `STRIPE_TEST_PUBLISHABLE_KEY` |
| PayPal | `PAYPAL_SANDBOX_CLIENT_ID`, `PAYPAL_SANDBOX_CLIENT_SECRET` |
| Braintree | `BRAINTREE_MERCHANT_ID`, `BRAINTREE_PUBLIC_KEY`, `BRAINTREE_PRIVATE_KEY` |
| Shopify | `SHOPIFY_SHOP` (full `*.myshopify.com` domain), `SHOPIFY_CLIENT_ID`, `SHOPIFY_CLIENT_SECRET`, `SHOPIFY_VARIANT_ID` (GraphQL ID) |
| x402 | `X402_FUNDING_PRIVATE_KEY` |
| Browserbase | `BROWSERBASE_API_KEY`, `BROWSERBASE_PROJECT_ID` (plan must support keep-alive sessions) |
| Kernel | `KERNEL_API_KEY` |

Native `task.toml` metadata records `scenario_id`, `prompt_condition` and
`required_method`; cart tasks add `store = "cart"` and `source_task`. Preflight
uses the source scenario for credential checks. Both tasks of a pair share the
discover task's `scenario_id`.

Run the oracle matrix on Daytona:

```sh
npm run bench:daytona:oracle -- --task-suite checkout --profile all \
  --env-file /path/to/.env.local-checkout --concurrency 2 \
  --agent-image "$(npm run --silent agent-image:ref)" \
  --verifier-image "$(npm run --silent verifier-image:ref)"
```

Use the same flags with `bench:daytona:agent:dev` for one model attempt per task
(`--model` picks it), adding `--agent-concurrency` at or below the trial
concurrency. Run the six-model baseline (three models per provider, with Claude
Code and Codex versions pinned through native Harbor agent kwargs):

```sh
npm run bench:production -- --task-suite checkout --profile all \
  --models-config config/models.checkout.yaml --n-attempts 1 \
  --concurrency 2 --agent-concurrency 2 --env-file /path/to/.env.local-checkout \
  --agent-image "$(npm run --silent agent-image:ref)" \
  --verifier-image "$(npm run --silent verifier-image:ref)"
```

The full matrix is 36 tasks × 3 profiles × 6 models = 648 trials per attempt;
`pass_5` needs `--n-attempts 5` (3,240 trials). Use
`--n-attempts 1 --max-retries 0` to keep one native attempt per cell: Harbor deletes earlier
exception-attempt directories when it retries, so rerun infrastructure failures
separately to keep their evidence apart from agent failures.

Narrow a run with `--task-filter`: `'*-discover'`, `'*-directed'`, `'*-cart-*'`,
or one pair such as `'stripe-card-*'`; no prompt-mode flag is needed. Concurrency
is per job, so `--profile all` can start three times as many trials; provider
plans must allow those sessions. Wallets and Link identities are independent, so
the runner does not otherwise cap concurrency.

### Browser profiles

`--profile local` (also the default, including the `docs` default),
`browserbase` or `kernel` vary browser infrastructure while keeping the browser
tool identical; `--profile all` launches three ordinary Harbor jobs with all 36
tasks each, and model trials keep the shared pair ID. Profiles are staged at
run time by the existing task-copy pipeline, with no extra task directories or
runner, and other suites' profiles are unaffected.

- Every profile extends the same task-pinned Playwright MCP image at
  `http://browser:8931/mcp`, with the same tools, US English locale, UTC
  timezone and 1280x720 viewport. Page-published WebMCP tools are disabled.
  Browser output files are shared read-only with the agent at the absolute
  paths MCP returns. Prompts, wallets, merchants, oracles, verifiers and rewards
  are identical; agents are not restricted to the browser.
- `shared/checkout/browser/` holds the common page hook and cloud session
  sidecar. The hook routes `http://merchant:3000` requests, including POST
  bodies, cookies and redirects, through the local MCP process, so a cloud
  browser reaches its trial's private merchant without a public URL; hosted
  Stripe and PayPal traffic runs in the selected browser.
- Each cloud trial creates its own provider session. API keys and the
  authenticated upstream CDP URL stay in a trusted sidecar that relays only that
  trial's CDP connection. Sessions are released when Compose stops, with a
  40-minute sidecar lifetime and the provider timeout as fallbacks.
- Browserbase uses direct egress with CAPTCHA solving disabled; Kernel uses
  headless, non-stealth browsers. Chromium versions and network latency can
  still differ: the matrix compares infrastructure through a common tool, not
  identical browser binaries.
- Staged metadata records `browser_profile`, and the native agent config keeps
  `CHECKOUT_BROWSER_PROFILE` so it survives removal of the staged files. Setup
  time stays separate from agent execution time.

## Authoring

The nine notebook discover tasks own their merchant, wallet service
(`environment/wallet/`), oracle and payment check (`tests/payment_check.py`);
edit those there. Shared files are canonical in `shared/checkout/`, and
`npm run sync` overwrites their copies in every task: Link setup
(`wallet/link_setup.js`), the shipping store, fixtures and `tests/check.py`
(`shipping/`), the grader, observation and quality criteria (`tests/`), and the
tool bundle (`agent/`, into `environment/agent/` with its install appended to the
generated agent Dockerfile). Sync then generates the rest from
`config/tasks.yaml`:
`checkout.directed` names each directed peer, its method and instruction;
`checkout.cart` maps each source to a cart prefix, from which it builds
`<prefix>-discover` and `<prefix>-directed` with `shared/checkout/cart/`;
`checkout.order_totals` overrides a source's order total. Within a pair only the
task name, provenance marker, prompt-condition metadata and payment instruction
differ. Generated copies are marked as generated in GitHub diffs. Task-specific
correctness checks stay in each task.

Scaffold a new merchant (placeholders, not runnable until completed):

```sh
npm run task:new -- --suite checkout --name merchant-item
```

```text
tasks/checkout-v1/<merchant-item>/
├── README.md               # Harbor Hub overview
├── instruction.md          # Purchase request, address and shared prompt
├── task.toml               # Task resources and declared artifacts
├── environment/            # Agent image and merchant/browser sidecars
├── solution/solve.sh       # Oracle purchase, never shown to the agent
└── tests/                  # Independent, separate-environment verifier
```

Use Harbor's multi-container environment for the merchant and browser. Keep
payment credentials and expected answers out of the agent container. Declare
merchant-side evidence as extra `task.toml` artifacts after the required agent
trajectory. The verifier must confirm the requested items, permitted total,
completed order and matching provider or chain payment, and reject duplicate
orders or charges.

Before publishing, run each task's oracle on Daytona and one unpaid trial that
scores zero, verify the Link-only page excludes direct card entry, refresh the
dataset manifest and run the repository checks. After publication, changes to
prompts, fixtures, verification or scoring follow the benchmark-major versioning
rule.
