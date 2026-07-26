# evalkit

`evalkit` is the deterministic Python authoring layer for the Harbor tasks in
this repository. It compiles typed suite declarations into ordinary Harbor task
directories. Harbor remains responsible for executing, validating, packaging,
and publishing those directories.

The existing [`tasks/`](../tasks) tree remains the source of truth during this
incremental rollout. Compiler output belongs in an ignored local directory,
usually `.cache/evalkit`; do not edit it by hand. Modify a declaration or its
source asset, rebuild, then review the generated diff before changing a task.

## Commands

Run commands from the repository root:

```bash
# Build every registered suite, or name one or more suites.
uv run python -m evalkit.cli build
uv run python -m evalkit.cli build tempo-v1

# Build a local mirror, verify it, then show definition differences.
uv run python -m evalkit.cli build --output-root .cache/evalkit
uv run python -m evalkit.cli check --output-root .cache/evalkit
uv run python -m evalkit.cli diff --output-root .cache/evalkit

# Validate declarations without writing output.
uv run python -m evalkit.cli lint tempo-v1

# Explain the files, source paths, locks, and overrides behind one output task.
uv run python -m evalkit.cli explain .cache/evalkit/tempo-v1/faucet-funded-transfer

# Resolve and pin a tag to an OCI index digest.
uv run python -m evalkit.cli lock --update image=ghcr.io/example/image:v1

# Create a skeleton declaration for a new Tempo task.
uv run python -m evalkit.cli new tempo-v1/my-task
```

`build`, `check`, `diff`, and `lint` accept zero or more suite names. With no
suite argument they operate on `tempo-v1`, `tempo-mcp-v1`, and `mpp`.

## Local Harbor smoke

After building a local mirror, run a representative task directly from it:

```bash
DOCKER_DEFAULT_PLATFORM=linux/amd64 uv run harbor run \
  --path .cache/evalkit/tempo-v1/faucet-funded-transfer \
  --agent oracle --env docker --n-concurrent 1 --yes
```

The published base images are AMD64-only, so Apple Silicon hosts need the
platform override. This task's independent on-chain correctness verifier can
pass without credentials. Its optional RewardKit quality score requires the
configured LLM credentials described in the repository root README.

## Build model

The compiler runs six deterministic stages:

1. **Load** a registered Python suite declaration.
2. **Validate** names, aliases, sources, image locks, environment declarations,
   and verifier adapter contracts.
3. **Lower** declarations into immutable assets, services, resolved images, and
   task metadata.
4. **Render** ordinary Harbor files.
5. **Hash** the rendered Harbor definition with Harbor-compatible file
   collection and hashing semantics.
6. **Emit** generated task directories and a provenance manifest.

Every generated task has `.evalkit-manifest.json`. It records each output asset,
its source and SHA-256, resolved image digests, aliases, and explicit override
reasons. Harbor does not include this manifest in its task content hash.

## Task declarations

Declarations live in `evalkit/suites/`. A task may wrap a current Harbor task
directory during migration, or describe files and environments directly.

```python
from evalkit.api import (
    DockerBuild,
    Environment,
    ImageRef,
    InstructionDoc,
    Suite,
    Task,
    copy,
    env,
)

SUITE = Suite(
    name="example-v1",
    tasks=(
        Task(
            name="example-v1/hello",
            copies=(copy("assets/solve.sh", "solution/solve.sh"),),
            instruction=InstructionDoc("# Hello\n\nProduce the required output.\n"),
            environment=Environment(
                agent=DockerBuild(ImageRef("ghcr.io/example/base", "v1")),
                variables=(env("API_URL", default="https://example.test"),),
            ),
            extra_config={"metadata": {"category": "integration"}},
        ),
    ),
)
```

Use `source=Path("tasks/.../my-task")` only for exact-parity migration. It
copies the task definition byte-for-byte, apart from the provenance manifest.
The current Tempo, Tempo MCP, and MPP suites use this bridge while their source
declarations are progressively made more granular.

### Public declaration reference

| Declaration | Purpose |
| --- | --- |
| `Suite`, `Policy` | Registered task collection and suite-wide lock/migration policy. |
| `Task`, `InstructionDoc`, `Solution` | One Harbor task, its prompt, and oracle assets. |
| `ImageRef`, `DockerBuild`, `Environment` | Locked images, Docker build inputs, variables, sidecars, and MCP servers. |
| `Copy`, `Bake`, `Fixture`, `Case` | Filesystem assets, image-layer assets, and explicit test parameterization. |
| `SharedVerifier`, `VerifierUse`, `AdapterContract` | Reusable verifier content and static adapter-symbol validation. |
| `Override` | Required rationale for intentionally replacing an output path. |

`Task.extra_config` is the escape hatch for Harbor TOML fields not yet modeled
by a typed declaration. Keep such usage small and move it into the typed API
when it becomes a repeated task pattern.

## Assets and collisions

`copy()` copies a file or directory into a task-relative destination.
`bake()` puts an asset in an agent or verifier Docker build context and produces
the corresponding Dockerfile. `fixture()` places a case fixture below
`tests/fixtures/`.

Two declarations cannot write the same destination by accident. Deliberately
replacing a shared asset requires an explicit reason:

```python
Task(
    name="example-v1/override",
    copies=(copy("local/check.py", "tests/check.py"),),
    overrides=(override("tests/check.py", reason="task-specific verifier"),),
)
```

## Images, services, and MCP

`ImageRef` contains only a name and tag. For fully declared tasks, the compiler
resolves it through `evalkit.lock` and renders the OCI index digest into the
Dockerfile or service configuration. Inline digests are intentionally not part
of declarations. `evalkit lock --update` writes the required digest. Exact-parity
`source=` migration declarations preserve their existing Dockerfiles and do not
declare `ImageRef`s until those files are migrated.

`runtime_service()` declares a Docker sidecar. `runtime_mcp()` creates an
agent MCP configuration asset and records the access profile. Both are lowered
into the task IR and rendered deterministically.

## Verifiers and cases

`SharedVerifier` declares shared verifier assets. `AdapterContract` lists the
Python symbols a task-local adapter must provide. The compiler reads adapter
syntax with `ast`; it never imports task code while validating a contract.

`Case` groups fixture files and environment values. Keep parameterization
explicit: use normal Python loops to create multiple `Task` declarations rather
than a hidden matrix abstraction.

## Compatibility checks

`evalkit.harbor_compat` matches Harbor's packaging behavior:

- `task.toml`, `instruction.md`, and `README.md` are included when present.
- Regular files below `environment/`, `tests/`, `solution/`, and `steps/` are
  included recursively.
- A task `.gitignore` replaces Harbor's default ignore patterns.
- Paths and per-file hashes are sorted before the final SHA-256 is calculated.

`npm run check:evalkit` validates every declaration. The evalkit test suite
builds disposable output and verifies Harbor hash parity; `npm run check` runs
that suite along with all existing repository checks.

## Tests and coverage

`npm run test:evalkit` runs the unit suite and enforces its 99% line-and-branch
coverage floor for production EvalKit modules. It covers declarations, compiler
behavior, Harbor-compatible hashing, image locks, and CLI diagnostics. Keep
Docker execution as a separate local smoke check: it validates the external
Harbor runtime rather than compiler branches.

The compiler itself is separately held to the same 99% floor, so broad API and
data-model coverage cannot mask untested compiler paths.
