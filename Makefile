.PHONY: help sync dataset benchmark benchmark-oracle check-agent-auth benchmark-agents benchmark-model view lint test check check-dataset check-generated clean-jobs clean

JOB_NAME ?= tempo-bench-model-local
ORACLE_JOB_NAME ?= tempo-bench-oracle-local
AGENT_JOB_NAME ?= tempo-bench-agents-local-$(shell date +%Y%m%d-%H%M%S)
AGENT ?= claude-code
MODEL ?= haiku
TASK_FILTER ?=
N_TASKS ?=
TASKS ?= tasks
N_CONCURRENT ?= $(shell sysctl -n hw.logicalcpu 2>/dev/null || nproc 2>/dev/null || echo 4)
MODEL_ARGS = $(if $(MODEL),--model '$(MODEL)',)
TASK_FILTER_ARGS = $(if $(TASK_FILTER),--include-task-name '$(TASK_FILTER)',)
N_TASKS_ARGS = $(if $(N_TASKS),--n-tasks $(N_TASKS),)
CONCURRENCY_ARGS = --n-concurrent $(N_CONCURRENT)

help:
	@printf '%s\n' \
		'Targets:' \
		'  make sync        Sync shared verifier/RewardKit/sidecar assets into tasks' \
		'  make dataset     Refresh Harbor task digests' \
		'  make benchmark   Run one harness/model (AGENT=claude-code MODEL=haiku by default)' \
		'  make benchmark-oracle Run Harbor oracle baseline (ORACLE_JOB_NAME=...)' \
		'  make benchmark-agents Run Claude Code benchmark (AGENT_JOB_NAME=...)' \
		'  make benchmark-model Alias for benchmark' \
		'  make check-agent-auth Verify Claude Code and quality judge auth is available' \
		'  make benchmark* N_CONCURRENT=4 Override Harbor trial concurrency' \
		'  make view        Open Harbor job viewer' \
		'  make lint        Run Ruff and syntax checks' \
		'  make test        Build task solution packages' \
		'  make check       Sync dataset, run lint checks, and build task solutions' \
		'  make check-dataset Verify dataset digests are fresh' \
		'  make check-generated Verify sync leaves no generated diff' \
		'  make clean-jobs  Remove local Harbor job outputs' \
		'  make clean       Remove generated local caches and job outputs'

sync:
	node scripts/sync-shared.mjs

dataset: sync
	harbor sync $(TASKS)

benchmark: dataset
	harbor run --path $(TASKS) --agent $(AGENT) $(MODEL_ARGS) $(TASK_FILTER_ARGS) $(N_TASKS_ARGS) $(CONCURRENCY_ARGS) --job-name $(JOB_NAME) -y

benchmark-oracle: dataset
	harbor run -c job.yaml $(CONCURRENCY_ARGS) --job-name $(ORACLE_JOB_NAME) -y

check-agent-auth:
	@if env | grep -q '^CLAUDE_FORCE_OAUTH=$$'; then \
		printf '%s\n' 'Invalid Claude Code auth: CLAUDE_FORCE_OAUTH is set but empty. Set it to 1/true or unset it.'; \
		exit 1; \
	fi
	@if [ -z "$$ANTHROPIC_API_KEY$$ANTHROPIC_AUTH_TOKEN$$CLAUDE_CODE_OAUTH_TOKEN" ]; then \
		printf '%s\n' 'Missing Claude Code auth: set ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or CLAUDE_CODE_OAUTH_TOKEN before running agent evals.'; \
		printf '%s\n' 'For subscription auth, run `claude setup-token`, export CLAUDE_CODE_OAUTH_TOKEN, and optionally set CLAUDE_FORCE_OAUTH=1.'; \
		exit 1; \
	fi
	@if [ -z "$$ANTHROPIC_API_KEY$$ANTHROPIC_AUTH_TOKEN" ]; then \
		printf '%s\n' 'Missing verifier judge auth: set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN for RewardKit quality judging.'; \
		exit 1; \
	fi

benchmark-agents: check-agent-auth dataset
	harbor run -c job.agents.yaml $(CONCURRENCY_ARGS) --job-name $(AGENT_JOB_NAME) -y

benchmark-model: benchmark

view:
	harbor view jobs

lint:
	ruff format --check .
	ruff check .
	find shared/verifier tasks/*/tests/tempo-bench-verifier -path '*/node_modules' -prune -o -type f -name '*.js' -print0 | xargs -0 -n1 node -c
	python3 -c 'from pathlib import Path; [compile(p.read_text(), str(p), "exec") for root in [Path("shared/rewardkit"), Path("shared/rewardkit-package"), *Path("tasks").glob("*/tests")] for p in root.rglob("*.py") if "node_modules" not in p.parts]'
	find shared/rewardkit tasks/*/tests tasks/*/solution -path '*/node_modules' -prune -o -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n
	find shared/rewardkit tasks/*/tests tasks/*/solution -path '*/node_modules' -prune -o -type f -name '*.sh' -print0 | xargs -0 shellcheck

test:
	find tasks -path '*/solution/package.json' -print0 | xargs -0 -n1 sh -c 'dir=$$(dirname "$$0"); rm -rf "$$dir/node_modules" "$$dir/package-lock.json"; trap '\''rm -rf "$$dir/node_modules" "$$dir/package-lock.json"'\'' EXIT; npm --prefix "$$dir" install --ignore-scripts --no-package-lock && npm --prefix "$$dir" run build'

check: dataset lint test

check-dataset: dataset
	git diff --exit-code tasks/dataset.toml

check-generated: dataset
	git diff --exit-code

clean-jobs:
	rm -rf jobs/*

clean: clean-jobs
	find . -name node_modules -type d -prune -exec rm -rf {} +
	find . -name package-lock.json -type f -delete
