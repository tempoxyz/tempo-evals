#!/bin/bash

# Tempo Bench keeps one task-specific canary at the start of instruction.md.
# The task linter validates uniqueness across the full benchmark; this check
# validates the changed task has a correctly formatted canary.

set -e

CANARY_PATTERN='^<!-- tempo-bench-canary: [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12} -->$'

if [ $# -eq 0 ]; then
    TASK_DIRS=$(find tasks -mindepth 2 -maxdepth 2 -type d)
else
    TASK_DIRS="$*"
fi

if [ -z "$TASK_DIRS" ]; then
    echo "No task directories to check"
    exit 0
fi

FAILED=0
for task_dir in $TASK_DIRS; do
    instruction="$task_dir/instruction.md"
    if [ ! -f "$instruction" ]; then
        echo "FAIL $task_dir: missing instruction.md"
        FAILED=1
    elif ! head -n 1 "$instruction" | grep -Eq "$CANARY_PATTERN"; then
        echo "FAIL $instruction: missing Tempo Bench canary comment"
        FAILED=1
    fi
done

if [ "$FAILED" -eq 1 ]; then
    exit 1
fi

echo "All task instructions contain a Tempo Bench canary"
