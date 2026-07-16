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
    agent_dockerfile="$task_dir/environment/Dockerfile"
    verifier_dockerfile="$task_dir/tests/Dockerfile"

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

    if [ ! -f "$agent_dockerfile" ] || [ ! -f "$verifier_dockerfile" ]; then
        echo "FAIL $task_dir: missing agent or verifier Dockerfile"
        FAILED=1
        continue
    fi

    agent_ref=$(awk 'toupper($1) == "FROM" { ref = $2 } END { print ref }' "$agent_dockerfile")
    verifier_ref=$(awk 'toupper($1) == "FROM" { ref = $2 } END { print ref }' "$verifier_dockerfile")
    if ! printf '%s\n' "$agent_ref" | grep -Eq '^.+:agent-source-[0-9a-f]{64}$' \
        || ! printf '%s\n' "$verifier_ref" | grep -Eq '^.+:verifier-source-[0-9a-f]{64}$' \
        || [ "${agent_ref%:agent-source-*}" != "${verifier_ref%:verifier-source-*}" ] \
        || [ "${agent_ref##*:agent-source-}" != "${verifier_ref##*:verifier-source-}" ]; then
        echo "FAIL $task_dir: Dockerfiles must use a matching agent/verifier source pair"
        FAILED=1
    fi

    if ! grep -qE '^[[:space:]]*(COPY|ADD)[[:space:]].*[[:space:]]/tests/?([[:space:]]|$)' "$verifier_dockerfile"; then
        echo "FAIL $verifier_dockerfile: must COPY or ADD the test context into /tests"
        FAILED=1
    fi
done

if [ "$FAILED" -ne 0 ]; then
    exit 1
fi

echo "All tasks use separate verifier environments"
