#!/usr/bin/env python3
"""Validate shared task conventions across Tempo Bench suites."""

from __future__ import annotations

import argparse
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANARY_PATTERN = re.compile(
    r"<!-- tempo-bench-canary: [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12} -->"
)


@dataclass(frozen=True)
class Suite:
    path: str
    required_files: tuple[str, ...]
    artifacts: tuple[str, ...]
    sidecar_artifacts: tuple[tuple[str, str], ...] = ()

    def task_name(self, slug: str) -> str:
        if self.path == "tasks/mpp":
            return f"tempo/mpp-{slug}"
        return f"{Path(self.path).name}/{slug}"


SUITES = (
    Suite(
        "tasks/tempo-v1",
        (
            "README.md",
            "instruction.md",
            "task.toml",
            "environment/Dockerfile",
            "solution/solve.sh",
            "tests/Dockerfile",
            "tests/test.sh",
        ),
        (
            "/app/package.json",
            "/app/tsconfig.json",
            "/app/src",
            "/logs/agent/trajectory.json",
        ),
    ),
    Suite(
        "tasks/mpp",
        (
            "README.md",
            "instruction.md",
            "task.toml",
            "environment/Dockerfile",
            "solution/solve.sh",
            "tests/Dockerfile",
            "tests/test.sh",
        ),
        (
            "/app/package.json",
            "/app/tsconfig.json",
            "/app/src",
            "/logs/agent/trajectory.json",
        ),
    ),
    Suite(
        "tasks/tempo-mcp-v1",
        (
            "README.md",
            "instruction.md",
            "task.toml",
            "environment/Dockerfile",
            "solution/solve.sh",
            "tests/Dockerfile",
            "tests/test.sh",
            "tests/expected.json",
        ),
        ("/app/answer.json",),
        (
            ("/var/log/tempo-mcp/direct-trace.jsonl", "tempo-mcp-direct"),
            ("/var/log/tempo-mcp/code-trace.jsonl", "tempo-mcp-code"),
        ),
    ),
)


def task_directories(root: Path, suite: Suite) -> list[Path]:
    suite_root = root / suite.path
    return sorted(
        path
        for path in suite_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def lint_task(root: Path, suite: Suite, task_dir: Path) -> list[str]:
    errors = []
    for relative_path in suite.required_files:
        if not (task_dir / relative_path).is_file():
            errors.append(f"{task_dir}: missing {relative_path}")

    instruction = task_dir / "instruction.md"
    if instruction.is_file() and not CANARY_PATTERN.search(instruction.read_text()):
        errors.append(f"{instruction}: missing a tempo-bench canary comment")

    metadata_path = task_dir / "task.toml"
    if not metadata_path.is_file():
        return errors
    try:
        metadata = tomllib.loads(metadata_path.read_text())
        actual_name = metadata["task"]["name"]
    except (KeyError, tomllib.TOMLDecodeError) as error:
        errors.append(f"{metadata_path}: invalid task metadata ({error})")
        return errors

    expected_name = suite.task_name(task_dir.name)
    if actual_name != expected_name:
        errors.append(
            f"{metadata_path}: task.name must be {expected_name!r}, got {actual_name!r}"
        )
    expected_artifacts: list[object] = [*suite.artifacts]
    expected_artifacts.extend(
        {"source": source, "service": service}
        for source, service in suite.sidecar_artifacts
    )
    if metadata.get("artifacts") != expected_artifacts:
        errors.append(f"{metadata_path}: artifacts must be {expected_artifacts!r}")
    verifier = metadata.get("verifier")
    if not isinstance(verifier, dict) or verifier.get("environment_mode") != "separate":
        errors.append(f'{metadata_path}: verifier.environment_mode must be "separate"')
    return errors


def lint(root: Path = ROOT) -> list[str]:
    errors = []
    canaries: dict[str, Path] = {}
    for suite in SUITES:
        for task_dir in task_directories(root, suite):
            errors.extend(lint_task(root, suite, task_dir))
            instruction = task_dir / "instruction.md"
            if not instruction.is_file():
                continue
            match = CANARY_PATTERN.search(instruction.read_text())
            if not match:
                continue
            canary = match.group(0)
            previous = canaries.get(canary)
            if previous:
                errors.append(
                    f"{instruction}: duplicate canary also used by {previous}"
                )
            else:
                canaries[canary] = instruction
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    errors = lint(args.root.resolve())
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print("Task lint passed.")


if __name__ == "__main__":
    main()
