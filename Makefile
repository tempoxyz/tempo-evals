.PHONY: help sync dataset benchmark benchmark-agents view check clean-jobs clean

JOB_NAME ?= tempo-bench-local
AGENT_JOB_NAME ?= tempo-bench-agents-local
TASKS ?= tasks

help:
	@printf '%s\n' \
		'Targets:' \
		'  make sync        Sync shared verifier/RewardKit/sidecar assets into tasks' \
		'  make dataset     Refresh Harbor task digests' \
		'  make benchmark   Run Harbor oracle benchmark (JOB_NAME=...)' \
		'  make benchmark-agents Run Codex and Claude Code benchmark (AGENT_JOB_NAME=...)' \
		'  make view        Open Harbor job viewer' \
		'  make check       Syntax-check shared JS/Python and sync dataset' \
		'  make clean-jobs  Remove local Harbor job outputs' \
		'  make clean       Remove generated local caches and job outputs'

sync:
	node scripts/sync-shared.mjs

dataset: sync
	harbor sync $(TASKS)

benchmark: dataset
	harbor run -c job.yaml --job-name $(JOB_NAME) -y

benchmark-agents: dataset
	harbor run -c job.agents.yaml --job-name $(AGENT_JOB_NAME) -y

view:
	harbor view jobs

check: dataset
	find shared/verifier tasks/*/tests/tempo-bench-verifier -path '*/node_modules' -prune -o -type f -name '*.js' -print0 | xargs -0 -n1 node -c
	python3 -c 'from pathlib import Path; [compile(p.read_text(), str(p), "exec") for root in [Path("shared/rewardkit"), *Path("tasks").glob("*/tests")] for p in root.rglob("*.py") if "node_modules" not in p.parts]'
	find shared/rewardkit tasks/*/tests tasks/*/solution -path '*/node_modules' -prune -o -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n

clean-jobs:
	rm -rf jobs/*

clean: clean-jobs
	find . -name node_modules -type d -prune -exec rm -rf {} +
	find . -name package-lock.json -type f -delete
