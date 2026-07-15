#!/bin/bash

# Separate verifier tasks use Harbor's native verifier environment and bake
# their test context into that environment's image.

set -e

if [ $# -eq 0 ]; then
    TASK_DIRS=$(find tasks -mindepth 2 -maxdepth 2 -type d -exec test -f {}/task.toml \; -print)
else
    TASK_DIRS="$*"
fi

if [ -z "$TASK_DIRS" ]; then
    echo "No tasks to check"
    exit 0
fi

FAILED=0
for task_dir in $TASK_DIRS; do
    toml="$task_dir/task.toml"
    dockerfile="$task_dir/tests/Dockerfile"

    if [ ! -f "$toml" ]; then
        echo "FAIL $task_dir: missing task.toml"
        FAILED=1
        continue
    fi

    if ! awk '
        /^[[:space:]]*\[verifier\][[:space:]]*(#.*)?$/ { in_verifier = 1; next }
        /^[[:space:]]*\[/ { in_verifier = 0 }
        in_verifier && /^[[:space:]]*environment_mode[[:space:]]*=[[:space:]]*"separate"[[:space:]]*(#.*)?$/ { found = 1 }
        END { exit found ? 0 : 1 }
    ' "$toml"; then
        echo "FAIL $toml: [verifier] environment_mode must be \"separate\""
        FAILED=1
        continue
    fi

    if [ ! -f "$dockerfile" ]; then
        echo "FAIL $task_dir: missing tests/Dockerfile"
        FAILED=1
        continue
    fi

    if ! grep -qE '^[[:space:]]*(COPY|ADD)[[:space:]].*[[:space:]]/tests/?([[:space:]]|$)' "$dockerfile"; then
        echo "FAIL $dockerfile: must COPY or ADD the test context into /tests"
        FAILED=1
    fi
done

if [ "$FAILED" -ne 0 ]; then
    exit 1
fi

echo "All tasks use separate verifier environments"
