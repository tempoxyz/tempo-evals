#!/bin/bash

# Return 0 when a task is exempt from a static check, 1 when it is not, and 2
# when the registry does not match the constrained YAML format documented in
# exceptions.yml. This avoids adding a YAML runtime dependency to CI.

set -e

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <exceptions.yml> <check-script> <task-directory>" >&2
    exit 2
fi

python3 - "$@" <<'PYEOF'
import re
import sys
from pathlib import Path

registry_path, check, task_dir = sys.argv[1:]
sets = {}
exceptions = {}
section = None
current_set = None

try:
    lines = Path(registry_path).read_text(encoding="utf-8").splitlines()
except OSError as error:
    print(f"Could not read exception registry: {error}", file=sys.stderr)
    sys.exit(2)

for number, raw_line in enumerate(lines, start=1):
    line = raw_line.split("#", maxsplit=1)[0].rstrip()
    if not line:
        continue
    if re.fullmatch(r"version: [1-9][0-9]*", line):
        continue
    if line == "task_sets:":
        section = "task_sets"
        current_set = None
        continue
    if line == "exceptions:":
        section = "exceptions"
        current_set = None
        continue
    if section == "task_sets":
        match = re.fullmatch(r"  ([A-Za-z0-9][A-Za-z0-9_-]*):", line)
        if match:
            current_set = match.group(1)
            sets[current_set] = []
            continue
        match = re.fullmatch(r"    - (tasks/[A-Za-z0-9._/-]+)", line)
        if match and current_set:
            sets[current_set].append(match.group(1))
            continue
    elif section == "exceptions":
        match = re.fullmatch(r"  ([A-Za-z0-9._-]+): ([A-Za-z0-9][A-Za-z0-9_-]*)", line)
        if match:
            exceptions[match.group(1)] = match.group(2)
            continue
    print(f"Invalid exceptions.yml at line {number}: {raw_line}", file=sys.stderr)
    sys.exit(2)

if not sets or not exceptions:
    print("exceptions.yml must define task_sets and exceptions", file=sys.stderr)
    sys.exit(2)

unknown_sets = sorted(set(exceptions.values()) - set(sets))
if unknown_sets:
    print(f"exceptions.yml references unknown task set(s): {', '.join(unknown_sets)}", file=sys.stderr)
    sys.exit(2)

sys.exit(0 if task_dir in sets.get(exceptions.get(check, ""), []) else 1)
PYEOF
