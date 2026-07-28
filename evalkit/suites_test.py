"""Tests for legacy migration and Tempo suite discovery declarations."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from evalkit.api import Task
from evalkit.suites import legacy, tempo_v1


class LegacySuiteTest(unittest.TestCase):
    def test_suite_from_directory_skips_non_tasks_and_preserves_dataset_path(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory)
            (source / "not-a-task").mkdir()
            task = source / "task"
            task.mkdir()
            (task / "task.toml").write_text("[task]\nname = 'example/task'\n")

            suite = legacy.suite_from_directory("example", source)

            self.assertEqual([task.name for task in suite.tasks], ["example/task"])
            self.assertEqual(suite.dataset_source, source / "dataset.toml")

    def test_suite_from_directory_rejects_non_string_task_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory)
            task = source / "task"
            task.mkdir()
            (task / "task.toml").write_text("[task]\nname = 1\n")
            with self.assertRaisesRegex(ValueError, "must be a string"):
                legacy.suite_from_directory("example", source)


class TempoSuiteTest(unittest.TestCase):
    def test_discovery_adds_typed_task_modules_and_rejects_invalid_exports(
        self,
    ) -> None:
        module_path = SimpleNamespace(stem="tempo_v1_discovered")
        parent = SimpleNamespace(glob=lambda _: [module_path])
        file_path = SimpleNamespace(parent=parent)
        discovered = Task("tempo-v1/discovered")
        with (
            patch.object(tempo_v1, "Path", return_value=file_path),
            patch.object(
                tempo_v1, "import_module", return_value=SimpleNamespace(TASK=discovered)
            ),
        ):
            tasks = tempo_v1._tasks()
        self.assertIn(discovered.name, {task.name for task in tasks})

        with (
            patch.object(tempo_v1, "Path", return_value=file_path),
            patch.object(
                tempo_v1,
                "import_module",
                return_value=SimpleNamespace(__name__="discovered", TASK=object()),
            ),
            self.assertRaisesRegex(TypeError, "must be an evalkit.api.Task"),
        ):
            tempo_v1._tasks()
