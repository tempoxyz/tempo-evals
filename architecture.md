# Architecture

Obrist is the Harbor-native benchmark authoring and compile layer for this
repository. Benchmark authors edit typed Python source packages; Obrist compiles
those packages into disposable Harbor workspaces. Running, viewing, publishing,
and result analysis remain direct Harbor workflows for now.

The current concrete benchmark collection is `tempobench`. The package boundary
is intentionally shaped so future collections, such as `mppbench`, can reuse the
same Obrist framework without importing Harbor directly.

## Goals

- Keep benchmark definitions read-only at runtime.
- Keep Obrist focused on compiling source packages into Harbor task workspaces.
- Generate Harbor task workspaces from typed Python specs.
- Keep Harbor-specific emission isolated in one package subtree.
- Make generated artifacts disposable and clearly marked as generated.
- Avoid adding run, view, diff, or result behavior on top of Harbor.

## Package Layout

```text
obrist/
  dsl/
  collections.py
  compiler/
  backends/harbor/
  cli.py
  registry.py
datasets/
  tempobench/
    collections.py
    spec.py
    solutions/
    shared/
  mppbench/
    README.md
tests/
```

`obrist` owns the reusable framework. `tempobench` owns Tempo-specific task
content. `mppbench` is currently only a documented future collection boundary.

## Runtime Flow

```text
tempobench/spec.py
    -> tempobench.collections.get_collection()
    -> obrist.collections.benchmark_job_collection()
    -> obrist.backends.harbor.emit.compile_collection()
    -> .generated/obrist/tempobench/
    -> harbor sync tasks
```

There is one generated default workspace for Tempo:

```text
.generated/obrist/tempobench/
```

After compile, use Harbor directly from the generated workspace:

```bash
cd .generated/obrist/tempobench
harbor run -c job.yaml -y
harbor view jobs --jobs
```

## Key Abstractions

### `BenchmarkCollection`

`BenchmarkCollection` is the loaded, read-only source package boundary. It
contains suites, jobs, tasks, repository paths, shared asset paths, and metadata.

Collections are loaded through:

- Python package entry points in `obrist.collections`
- explicit registration via `obrist.register`
- import fallback through `<collection>.collections.get_collection` or
  `datasets.<collection>.collections.get_collection`

`tempobench.collections` is deliberately small: it wraps the Tempo
`BenchmarkJobSpec` with the standard Obrist collection builder.

### `BenchmarkJobSpec`

`BenchmarkJobSpec` is the high-level authoring object for generated benchmark
jobs. It defines:

- collection and dataset names
- dataset metadata
- shared package paths
- profiles such as `docs` and `mcp`
- task cases
- suite/job settings
- environment, verifier, agent, and TypeScript app defaults
- execution constraints

For Tempo, `datasets/tempobench/spec.py` is the single source of
truth for task cases, profile overlays, environment fixtures, source-pattern
checks, and local oracle solution directories.

### `TaskCaseSpec`

`TaskCaseSpec` describes one benchmark intent before profile expansion. It
contains the prompt, requirements, verifier case, fixture environment, source
patterns, and oracle solution directory.

Examples of current Tempo cases include:

- `transfer-with-memo`
- `transfer-with-memo-fee-payer`
- `set-fee-token`
- `create-stablecoin-with-policy`
- `faucet-funded-transfer`
- `stablecoin-dex-swap`

### `ProfileSpec`

`ProfileSpec` expands each task case into a concrete task variant. Tempo
currently has:

- `docs`: exposes docs-oriented instructions and `TEMPO_DOCS_URL`.
- `mcp`: configures the official Tempo MCP server.

The concrete task name is derived from case plus profile:

```text
tempo/<case-slug>-<profile-suffix>
```

### `Suite`

Suites group jobs and configure attempts and job naming. Tempo currently uses a
single default suite. Additional suites should be reserved for real task-set or
compile-shape differences.

### `Harbor Backend`

`obrist.backends.harbor` is where Obrist becomes Harbor-specific. It owns:

- rendering Harbor `task.toml`, `instruction.md`, `dataset.toml`, and `job.yaml`
- copying packaged local oracle solutions
- materializing shared Docker, RewardKit, and verifier assets into each task
- adding generated headers to generated text files
- running `harbor sync tasks`

Only this subtree should shell out to Harbor or import Harbor-specific APIs.

## Generated Workspace

Compile writes a disposable Harbor workspace under `.generated/obrist`. For
Tempo, the default output is:

```text
.generated/obrist/tempobench/
  manifest.json
  job.yaml
  shared/
  tasks/
    dataset.toml
    <task>/
      task.toml
      instruction.md
      environment/
      solution/
      tests/
```

Generated text files that support comments receive an auto-generated header.
Strict JSON files stay valid JSON and carry generated metadata inside the JSON
payload instead.

Obrist refuses to compile into protected source paths such as:

- `obrist`
- `datasets/tempobench`
- `tasks`
- `shared`

## Source Assets

`tempobench` has no checked-in Harbor task tree. Source assets are packaged in
three places:

- `spec.py`: typed benchmark definitions and fixture values.
- `solutions/`: local oracle solution directories copied into generated tasks.
- `shared/`: reusable Docker, RewardKit, verifier, and MCP assets materialized
  into generated tasks.

This avoids symlink-heavy source task directories and keeps Harbor's required
self-contained task shape as generated output.

## Current Invariants

- `tempobench` imports Obrist, not Harbor.
- Harbor imports and shell-outs are isolated under `obrist.backends.harbor`.
- Generated workspaces live outside source packages.
- `tempobench` runtime state is read-only.
- Generated text files use generated headers when comments are valid for that
  file type.
- JSON remains strict JSON.
- Default Tempo compilation produces one workspace:
  `.generated/obrist/tempobench`.
- Agent choice happens in Harbor, after Obrist compiles the workspace.
- Python code is typed and checked with mypy.
- Python commands should run through `uv`.

## Not Implemented Yet

### Baseline Lift And A/B Arms

The original design describes baseline-lift measurement:

```text
score(docs arm) - score(no-docs baseline arm)
```

Current Obrist does not generate paired arms, no-docs baselines, docs@base,
docs@candidate workspaces, or any diffing behavior. It compiles one Harbor
workspace for the selected suite.

### Docs Bundle Pipeline

The original design calls for resolving docs sources to content-addressed
bundles and serving them through a generated docs MCP sidecar. Current Tempo
profiles either point at `TEMPO_DOCS_URL` or configure the remote Tempo MCP
server. There is no generic docs bundle builder or generated docs MCP sidecar
yet.

### Egress Enforcement And Preflight

The DSL has sandbox and egress types, but the current Harbor emitter does not
compile a default-deny network policy or run preflight leak checks. There is no
canary trial, egress log scan, or trajectory scan that invalidates leaking runs.

### Full Environment Model

The current generated task environment is a merged static map from defaults,
case, and profile. Missing pieces include:

- `inherit` secrets passed only as process environment
- secret redaction in manifests
- dynamic compile-time environment functions
- hashed resolved environment manifests
- one shared env map emitted into all relevant Harbor verifier/agent contexts

### Harbor Model Validation

Obrist currently renders Jinja templates and then runs `harbor sync tasks`, which
updates dataset digests and catches many Harbor-level issues. It does not yet
construct Harbor's own Pydantic models directly for every emitted file.

### Run, View, And Result Analysis

Obrist intentionally does not implement run, view, collect, table, or diff
commands. Use Harbor directly after compile. Not implemented:

- pass@k aggregation beyond Harbor attempts
- lift calculations
- quality/effort deltas
- per-task scorecards
- trajectory/log grep
- significance or threshold summaries
- stateless web UI over run bundles

### Persistence Sinks

S3/R2 sinks, object-store atomic manifest writes, and export workflows are not
implemented.

### Self-Contained Offline Images

The design calls for baked/offline dependencies and no network installs during
agent or verifier phases. Current tasks still rely on the existing Harbor/Docker
task setup and shared task assets. A fully self-contained image/offline package
cache is not implemented.

### Generalized Grader Lowering

The public DSL includes grader helpers such as `file_matches`, `onchain`,
`quality_rubric`, `all_of`, and `any_of`, but the current Tempo path primarily
uses `BenchmarkJobSpec` source patterns and shared RewardKit criteria templates.
A complete lowering path from every generic `Grader` node to Harbor/RewardKit is
not implemented.

## Design Direction

Near-term work should keep Obrist tightly coupled to Harbor as the runtime while
making the authoring API cleaner:

- keep benchmark collections as typed, read-only Python packages
- keep Harbor task shape generated, not authored by hand
- expand `BenchmarkJobSpec` before adding new abstractions
- add suites only for real benchmark variants
- leave agent/model selection, runs, viewing, and result analysis to Harbor
- implement docs bundles and baseline arms as first-class Obrist concepts when
  they are needed
