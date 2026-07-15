#!/bin/bash

# Tempo Bench prompts are immutable task contracts, so they do not carry the
# benchmark-template's generated timeout suffix. Require a terminal newline so
# any future task-specific suffix remains a distinct, intentional paragraph.

set -e

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
    elif [ -n "$(tail -c 1 "$instruction")" ]; then
        echo "FAIL $instruction: must end with a newline"
        FAILED=1
    fi
done

exit "$FAILED"
