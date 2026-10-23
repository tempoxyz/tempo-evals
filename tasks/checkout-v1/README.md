# Checkout Suite

Planned dataset: `tempo/checkout-bench-v1`. Sixteen Harbor tasks cover six
merchants with required shipping and discover/directed prompts. The dataset is not published.
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

### Prepared MPP tasks

Four additional tasks insert `-prepared-` before the prompt condition:
`mpp-card-prepared-discover`, `mpp-card-prepared-directed`,
`mpp-ousd-prepared-discover`, and `mpp-ousd-prepared-directed`.
They share their cold source's merchant, wallet, oracle and grading. The agent
image additionally installs pinned mppx, viem and tsx under `/opt/mpp-client`
and the prompt points to a generic client usage guide. This measures a prepared
client plus instructions, separately from cold discovery. It does not test
preinstallation alone or an already authenticated browser wallet.

`config/tasks.yaml` lists the source tasks; sync generates all prepared copies
from those sources and `shared/checkout/prepared/`. Metadata and exports record
`mpp_client_profile=prepared` (existing tasks export `cold`). Prepared and cold
results remain separate in quality summaries. Use
`--task-filter 'mpp-*-prepared-*'` to run the four new tasks with any browser
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

The six discover tasks are the authored sources. `config/tasks.yaml` declares
peer names and method instructions; `npm run sync` generates their standalone
directed task directories. Edit the source task to change a pair's merchant,
wallet setup, oracle, verifier, or scoring. Only the task name, provenance marker,
prompt-condition metadata, and added payment instruction differ within a pair.
Generated task copies are marked as generated in GitHub diffs.

`--task-suite checkout` runs all sixteen tasks, including oracle runs. Use
`--task-filter '*-discover'` for discover only, `--task-filter '*-directed'`
for directed only, or `--task-filter 'stripe-card-*'` for one merchant pair.
No prompt-mode flag is required. Each task and attempt receives a separate
Harbor environment, merchant instance, and funded wallet, including concurrent
runs.

Native `task.toml` fields record `scenario_id`, `prompt_condition`, and
`required_method`. Preflight reuses the scenario identity for credential checks.
Exports prefer the trial's staged task metadata and keep prompt conditions
separate in task and suite quality summaries. OUSD MPP's method is `tempo_mpp`; card MPP's method is `stripe_mpp`.

`observed_method` comes from provider or receipt evidence, including failed
checkouts. It is blank when unknown or when multiple methods were observed;
`observed_methods` retains the full set as a JSON array. Observing a method does
not imply success. The existing success-only `payment_method` column remains.
Shared observation and grading code lives in `shared/checkout/tests/` and is
copied into every checkout task by `npm run sync`.

## Required shipping

Every checkout task requires the same recipient and full shipping destination.
Shipping is part of the default task, alongside buying one Tempo Notebook for
$12; there are no separate shipping task variants.

The six discover tasks own their merchant adapters, provider snapshots and
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
available across all six merchants. Agents choose their own interaction tools.

Submitted destinations are stored as immutable, trial-local orders. The store
checks input structure, not whether it matches the expected answer. Payment
references use that shipping order ID. Stripe MPP credentials bind the order
through `externalId`; OUSD MPP challenges use an explicit per-order scope before
proxying the delivery endpoint. A shipping order cannot be changed after
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
from repeated Harbor trials. Provider sandbox payments and Tempo testnet
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

Run the ten tasks across all browser profiles with three models per provider:

```sh
npm run bench:production -- --task-suite checkout --profile all \
  --models-config config/models.checkout.yaml --n-attempts 1 \
  --concurrency 2 --agent-concurrency 2 --env-file /path/to/.env.local-checkout \
  --agent-image "$(npm run --silent agent-image:ref)" \
  --verifier-image "$(npm run --silent verifier-image:ref)"
```

The original ten-task baseline had 180 trials. The expanded sixteen-task suite
has 288 trials across three browser profiles and six models. The model configuration pins Claude Code and Codex
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
`credentialed_payment_request_count` is MPP's raw credential-bearing
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

All six merchant scenarios request one Tempo Notebook for at most $12 and use
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
Every trial runs the same wallet, Link enrollment, and browser services before
the agent starts. After Link enrollment, a shared Compose readiness step opens
the merchant through the selected browser. A broken browser connection fails
environment setup before the agent starts. The wallet service creates a fresh
Tempo testnet payer and confirms its faucet funding independently of other
trials. Link enrollment prepares a unique identity using a synthetic sandbox card. The agent sees the
same wallet fields and payment methods across tasks; merchant and verifier
sidecars differ. Cold MPP agents receive no preinstalled payment helper or payment
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
all sixteen tasks per job. Model trials retain the shared pair
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
