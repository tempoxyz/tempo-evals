#!/bin/bash

# Validate the common Tempo Bench task.toml contract. Suite-specific optional
# fields are intentionally not required here because the MCP suite has a
# different runtime configuration from the integration suites.

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
    task_toml="$task_dir/task.toml"
    if [ ! -f "$task_toml" ]; then
        echo "FAIL $task_dir: missing task.toml"
        FAILED=1
        continue
    fi

    RESULT=$(python3 - "$task_toml" <<'PYEOF'
import sys

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

path = sys.argv[1]
try:
    with open(path, "rb") as f:
        data = tomllib.load(f)
except Exception as error:
    print(f"invalid TOML: {error}")
    sys.exit(1)

required = (
    ("schema_version",),
    ("task", "name"),
    ("task", "description"),
    ("task", "keywords"),
    ("metadata", "category"),
    ("metadata", "benchmark"),
    ("verifier", "timeout_sec"),
    ("verifier", "environment_mode"),
    ("agent", "timeout_sec"),
)

for parts in required:
    value = data
    for part in parts:
        if not isinstance(value, dict) or part not in value:
            print("missing " + ".".join(parts))
            break
        value = value[part]
    else:
        if value in (None, "", []):
            print("empty " + ".".join(parts))
PYEOF
    ) || true

    if [ -n "$RESULT" ]; then
        while IFS= read -r line; do
            [ -n "$line" ] && echo "FAIL $task_toml: $line"
        done <<EOF
$RESULT
EOF
        FAILED=1
    fi
done

exit "$FAILED"
