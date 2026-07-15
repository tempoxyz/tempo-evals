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


def parse_registry(path: Path) -> dict[str, dict[str, list[str]]]:
    """Parse the constrained exceptions.yml schema."""
    exceptions: dict[str, dict[str, list[str]]] = {}
    section: str | None = None
    current_case: str | None = None
    current_list: str | None = None

    for number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.split("#", maxsplit=1)[0].rstrip()
        if not line or re.fullmatch(r"version: [1-9][0-9]*", line):
            continue
        if line == "exceptions:":
            section = "exceptions"
            current_case = None
            current_list = None
            continue
        if section == "exceptions":
            if match := re.fullmatch(r"  ([A-Za-z0-9][A-Za-z0-9_-]*):", line):
                current_case = match.group(1)
                exceptions[current_case] = {"checks": [], "files": []}
                current_list = None
                continue
            if line in {"    checks:", "    files:"} and current_case:
                current_list = line.strip(": ")
                continue
            if current_list == "checks" and (
                match := re.fullmatch(r"      - ([A-Za-z0-9._-]+)", line)
            ):
                exceptions[current_case][current_list].append(match.group(1))
                continue
            if current_list == "files" and (
                match := re.fullmatch(r"      - (tasks/[A-Za-z0-9._/-]+)", line)
            ):
                exceptions[current_case][current_list].append(match.group(1))
                continue
        raise ValueError(f"invalid exceptions.yml at line {number}: {raw_line}")

    if not exceptions:
        raise ValueError("exceptions.yml must define at least one exception case")
    incomplete_cases = sorted(
        name
        for name, exception in exceptions.items()
        if not exception["checks"] or not exception["files"]
    )
    if incomplete_cases:
        cases = ", ".join(incomplete_cases)
        raise ValueError(f"exception case(s) must define checks and files: {cases}")
    return exceptions


def main() -> int:
    if len(sys.argv) != 4:
        print(
            f"Usage: {sys.argv[0]} <exceptions.yml> <check-script> <task-directory>",
            file=sys.stderr,
        )
        return 2

    registry_path, check, task_dir = sys.argv[1:]
    try:
        exceptions = parse_registry(Path(registry_path))
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2

    return (
        0
        if any(
            check in exception["checks"] and task_dir in exception["files"]
            for exception in exceptions.values()
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
