.PHONY: help sync dataset benchmark benchmark-oracle benchmark-agents benchmark-model view check clean-jobs clean

JOB_NAME ?= tempo-bench-model-local
ORACLE_JOB_NAME ?= tempo-bench-oracle-local
AGENT_JOB_NAME ?= tempo-bench-agents-local
AGENT ?= claude-code
MODEL ?= haiku
TASK_FILTER ?=
N_TASKS ?=
TASKS ?= tasks
MODEL_ARGS = $(if $(MODEL),--model '$(MODEL)',)
TASK_FILTER_ARGS = $(if $(TASK_FILTER),--include-task-name '$(TASK_FILTER)',)
N_TASKS_ARGS = $(if $(N_TASKS),--n-tasks $(N_TASKS),)

help:
	@printf '%s\n' \
		'Targets:' \
		'  make sync        Sync shared verifier/RewardKit/sidecar assets into tasks' \
		'  make dataset     Refresh Harbor task digests' \
		'  make benchmark   Run one harness/model (AGENT=claude-code MODEL=haiku by default)' \
		'  make benchmark-oracle Run Harbor oracle baseline (ORACLE_JOB_NAME=...)' \
		'  make benchmark-agents Run Codex and Claude Code benchmark (AGENT_JOB_NAME=...)' \
		'  make benchmark-model Alias for benchmark' \
		'  make view        Open Harbor job viewer' \
		'  make check       Syntax-check shared JS/Python and sync dataset' \
		'  make clean-jobs  Remove local Harbor job outputs' \
		'  make clean       Remove generated local caches and job outputs'

sync:
	node scripts/sync-shared.mjs

dataset: sync
	harbor sync $(TASKS)

benchmark: dataset
	harbor run --path $(TASKS) --agent $(AGENT) $(MODEL_ARGS) $(TASK_FILTER_ARGS) $(N_TASKS_ARGS) --job-name $(JOB_NAME) -y

benchmark-oracle: dataset
	harbor run -c job.yaml --job-name $(ORACLE_JOB_NAME) -y

benchmark-agents: dataset
	harbor run -c job.agents.yaml --job-name $(AGENT_JOB_NAME) -y

benchmark-model: benchmark

view:
	harbor view jobs

check: dataset
	find shared/verifier tasks/*/tests/tempo-bench-verifier -path '*/node_modules' -prune -o -type f -name '*.js' -print0 | xargs -0 -n1 node -c
	find shared/rewardkit tasks/*/tests -path '*/node_modules' -prune -o -type f -name '*.py' -print0 | xargs -0 -n1 python3 -m py_compile
	find shared/rewardkit tasks/*/tests tasks/*/solution -path '*/node_modules' -prune -o -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n

clean-jobs:
	rm -rf jobs/*

clean: clean-jobs
	find . -name node_modules -type d -prune -exec rm -rf {} +
	find . -name package-lock.json -type f -delete
