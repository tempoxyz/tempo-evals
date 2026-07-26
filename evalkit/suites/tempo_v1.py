"""Tempo suite declarations."""

from importlib import import_module
from pathlib import Path

from evalkit.api import Suite, Task
from evalkit.compiler.build import ROOT
from evalkit.suites.legacy import suite_from_directory
from evalkit.suites.tempo_v1_faucet_funded_transfer import TASK as REPRESENTATIVE_TASK

SOURCE = ROOT / "tasks" / "tempo-v1"


LEGACY = suite_from_directory("tempo-v1", SOURCE)


def _tasks() -> tuple[Task, ...]:
    """Combine legacy parity declarations with newly scaffolded Tempo tasks."""
    tasks = [
        REPRESENTATIVE_TASK if task.name == REPRESENTATIVE_TASK.name else task
        for task in LEGACY.tasks
    ]
    for module_path in sorted(Path(__file__).parent.glob("tempo_v1_*.py")):
        if module_path.stem == "tempo_v1_faucet_funded_transfer":
            continue
        module = import_module(f"evalkit.suites.{module_path.stem}")
        task = module.TASK
        if not isinstance(task, Task):
            raise TypeError(f"{module.__name__}.TASK must be an evalkit.api.Task")
        tasks.append(task)
    return tuple(tasks)


SUITE = Suite(
    name="tempo-v1",
    dataset_source=LEGACY.dataset_source,
    tasks=_tasks(),
)
