.PHONY: help compile format check clean

OBRIST_OUT ?= .generated/obrist
OBRIST_PYTHONPATH = .
OBRIST = PYTHONPATH=$(OBRIST_PYTHONPATH) uv run obrist
TEMPOBENCH = datasets/tempobench
GENERATED_TASKS = $(OBRIST_OUT)/tempobench/tasks

# List the compiler-focused public workflow surface.
help:
	@printf '%s\n' \
		'Targets:' \
		'  make compile    Compile tempobench through Obrist' \
		'  make format     Auto-format Python sources' \
		'  make check      Run package, asset, unit, and type checks' \
		'  make clean      Remove generated workspaces and caches'

# Compile tempobench into one generated Obrist workspace.
compile:
	$(OBRIST) compile tempobench --out $(OBRIST_OUT)

# Auto-format Python sources with Ruff.
format:
	uv run ruff format obrist datasets tests
	uv run ruff check --fix obrist datasets tests

# Validate package assets and typed Python code.
check: compile
	uv run ruff format --check obrist datasets tests
	uv run ruff check obrist datasets tests
	find $(TEMPOBENCH)/shared/verifier $(GENERATED_TASKS)/*/tests/tempo-bench-verifier -path '*/node_modules' -prune -o -type f -name '*.js' -print0 | xargs -0 -n1 node -c
	uv run python -c 'from pathlib import Path; [compile(p.read_text(), str(p), "exec") for root in [Path("$(TEMPOBENCH)/shared/rewardkit"), Path("$(TEMPOBENCH)/shared/rewardkit-package"), *Path("$(GENERATED_TASKS)").glob("*/tests")] for p in root.rglob("*.py") if "node_modules" not in p.parts]'
	uv run python -m compileall -q obrist datasets tests
	PYTHONPATH=$(OBRIST_PYTHONPATH) uv run python -m unittest discover -s tests
	PYTHONPATH=$(OBRIST_PYTHONPATH) uv run --group dev mypy obrist datasets tests
	find $(TEMPOBENCH)/shared/rewardkit $(GENERATED_TASKS)/*/tests $(GENERATED_TASKS)/*/solution -path '*/node_modules' -prune -o -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n

# Remove generated local artifacts.
clean:
	rm -rf .generated
	find . -name node_modules -type d -prune -exec rm -rf {} +
	find . -name package-lock.json -type f -delete
	find obrist datasets tests -name __pycache__ -type d -prune -exec rm -rf {} +
