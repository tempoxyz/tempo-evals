"""Exact-parity declarations for existing Harbor task directories."""

from __future__ import annotations

import tomllib
from pathlib import Path

from evalkit.api import Suite, Task


def suite_from_directory(name: str, source: Path) -> Suite:
    """Wrap an existing suite while preserving byte-for-byte generated parity.

    ``task.toml`` supplies the canonical Harbor task name, avoiding assumptions
    about a directory name such as the MPP suite's ``tempo/mpp-*`` convention.
    """
    tasks = []
    for task_dir in sorted(path for path in source.iterdir() if path.is_dir()):
        task_toml = task_dir / "task.toml"
        if not task_toml.is_file():
            continue
        metadata = tomllib.loads(task_toml.read_text())
        task_name = metadata["task"]["name"]
        if not isinstance(task_name, str):
            raise ValueError(f"{task_toml}: task.name must be a string")
        tasks.append(Task(task_name, source=task_dir))
    return Suite(name, tuple(tasks), dataset_source=source / "dataset.toml")
