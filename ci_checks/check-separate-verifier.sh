#!/bin/bash

# Validate verifier layout. Tempo Bench currently uses shared verifier images
# with dependencies supplied by the shared base image. Separate verifier tasks
# remain supported and must provide an isolated tests/Dockerfile.

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
    toml="$task_dir/task.toml"
    verifier_dockerfile="$task_dir/tests/Dockerfile"

    if [ ! -f "$toml" ]; then
        echo "FAIL $task_dir: missing task.toml"
        FAILED=1
        continue
    fi

    TOML_RESULT=$(python3 - "$toml" <<'PYEOF'
import os
import sys

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

try:
    with open(sys.argv[1], "rb") as f:
        data = tomllib.load(f)
except Exception as error:
    print(f"PARSE_ERROR: {error}")
    sys.exit()

verifier = data.get("verifier", {})
mode = verifier.get("environment_mode")
if mode not in {"shared", "separate"}:
    print("INVALID_MODE: [verifier] environment_mode must be shared or separate")
    sys.exit()

if mode == "shared":
    print("SHARED")
    sys.exit()

if "artifacts" in verifier:
    print("MISPLACED_ARTIFACTS: move artifacts from [verifier] to the top level")
    sys.exit()

parents = set()
for artifact in data.get("artifacts", []):
    if isinstance(artifact, str):
        source = artifact
    elif isinstance(artifact, dict) and not artifact.get("service"):
        source = artifact.get("source")
    else:
        continue
    if source:
        parent = os.path.dirname(source.rstrip("/"))
        if parent and parent != "/":
            parents.add(parent)

print("SEPARATE")
for parent in sorted(parents):
    print(f"PARENT:{parent}")
PYEOF
)

    case "$TOML_RESULT" in
        SHARED)
            echo "PASS $task_dir: shared verifier mode"
            continue
            ;;
        SEPARATE*)
            ;;
        *)
            echo "FAIL $toml: ${TOML_RESULT#*: }"
            FAILED=1
            continue
            ;;
    esac

    if [ ! -f "$verifier_dockerfile" ]; then
        echo "FAIL $task_dir: missing $verifier_dockerfile"
        FAILED=1
        continue
    fi

    if ! grep -qE '^\s*(COPY|ADD)\b.*[[:space:]]/tests(/|$|[[:space:]])' "$verifier_dockerfile"; then
        echo "FAIL $verifier_dockerfile: separate mode requires COPY/ADD into /tests"
        FAILED=1
        continue
    fi

    PARENTS=$(printf '%s\n' "$TOML_RESULT" | sed -n 's|^PARENT:||p')
    for parent in $PARENTS; do
        escaped_parent=$(printf '%s\n' "$parent" | sed 's|[][\\/.*^$]|\\&|g')
        if ! grep -qE "^\s*RUN[[:space:]].*mkdir[[:space:]]+(-p[[:space:]]+)?[^#]*(^|[[:space:]/])${escaped_parent}([[:space:]]|/|\$)" "$verifier_dockerfile"; then
            echo "FAIL $verifier_dockerfile: missing RUN mkdir -p for artifact parent $parent"
            FAILED=1
        fi
    done
done

exit "$FAILED"
