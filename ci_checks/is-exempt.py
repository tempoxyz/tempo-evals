#!/usr/bin/env python3
"""Return whether one task is exempt from one static check.

The exception registry deliberately uses a small YAML subset so static-check
CI does not need an additional YAML dependency. See exceptions.yml for the
supported schema and policy.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def parse_registry(path: Path) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Parse the constrained exceptions.yml schema."""
    sets: dict[str, list[str]] = {}
    exceptions: dict[str, str] = {}
    section: str | None = None
    current_set: str | None = None

    for number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.split("#", maxsplit=1)[0].rstrip()
        if not line or re.fullmatch(r"version: [1-9][0-9]*", line):
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
            if match := re.fullmatch(r"  ([A-Za-z0-9][A-Za-z0-9_-]*):", line):
                current_set = match.group(1)
                sets[current_set] = []
                continue
            if (
                match := re.fullmatch(r"    - (tasks/[A-Za-z0-9._/-]+)", line)
            ) and current_set:
                sets[current_set].append(match.group(1))
                continue
        elif section == "exceptions":
            if match := re.fullmatch(
                r"  ([A-Za-z0-9._-]+): ([A-Za-z0-9][A-Za-z0-9_-]*)", line
            ):
                exceptions[match.group(1)] = match.group(2)
                continue
        raise ValueError(f"invalid exceptions.yml at line {number}: {raw_line}")

    if not sets or not exceptions:
        raise ValueError("exceptions.yml must define task_sets and exceptions")
    unknown_sets = sorted(set(exceptions.values()) - set(sets))
    if unknown_sets:
        raise ValueError(
            f"exceptions.yml references unknown task set(s): {', '.join(unknown_sets)}"
        )
    return sets, exceptions


def main() -> int:
    if len(sys.argv) != 4:
        print(
            f"Usage: {sys.argv[0]} <exceptions.yml> <check-script> <task-directory>",
            file=sys.stderr,
        )
        return 2

    registry_path, check, task_dir = sys.argv[1:]
    try:
        sets, exceptions = parse_registry(Path(registry_path))
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    return 0 if task_dir in sets.get(exceptions.get(check, ""), []) else 1


if __name__ == "__main__":
    raise SystemExit(main())
