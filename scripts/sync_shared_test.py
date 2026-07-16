from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import sync_shared


class SyncSharedTest(unittest.TestCase):
    def test_tempo_tasks_are_discovered_from_authored_directories(self) -> None:
        original_tasks_dir = sync_shared.TASKS_DIR
        with tempfile.TemporaryDirectory() as temporary_directory:
            tasks_dir = Path(temporary_directory)
            for directory, name in (
                ("alpha", "tempo-v1/alpha"),
                ("beta", "tempo-v1/beta"),
                ("_templates/ignored", "tempo-v1/ignored"),
            ):
                task_dir = tasks_dir / directory
                task_dir.mkdir(parents=True)
                (task_dir / "task.toml").write_text(f'[task]\nname = "{name}"\n')

            sync_shared.TASKS_DIR = tasks_dir
            try:
                self.assertEqual(
                    sync_shared.tempo_task_names(),
                    ["tempo-v1/alpha", "tempo-v1/beta"],
                )
            finally:
                sync_shared.TASKS_DIR = original_tasks_dir

    def test_syncs_both_dockerfiles_for_every_suite(self) -> None:
        original_dirs = (
            sync_shared.TASKS_DIR,
            sync_shared.MPP_TASKS_DIR,
            sync_shared.MCP_TASKS_DIR,
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            suite_dirs = tuple(root / name for name in ("tempo", "mpp", "mcp"))
            for suite_dir in suite_dirs:
                task_dir = suite_dir / "example"
                task_dir.mkdir(parents=True)
                (task_dir / "task.toml").write_text('[task]\nname = "example"\n')

            (
                sync_shared.TASKS_DIR,
                sync_shared.MPP_TASKS_DIR,
                sync_shared.MCP_TASKS_DIR,
            ) = suite_dirs
            try:
                self.assertEqual(sync_shared.sync_task_dockerfiles(), 3)
                for suite_dir in suite_dirs:
                    task_dir = suite_dir / "example"
                    self.assertEqual(
                        (task_dir / "environment" / "Dockerfile").read_text(),
                        sync_shared.ENVIRONMENT_DOCKERFILE,
                    )
                    self.assertEqual(
                        (task_dir / "tests" / "Dockerfile").read_text(),
                        sync_shared.VERIFIER_DOCKERFILE,
                    )
            finally:
                (
                    sync_shared.TASKS_DIR,
                    sync_shared.MPP_TASKS_DIR,
                    sync_shared.MCP_TASKS_DIR,
                ) = original_dirs


if __name__ == "__main__":
    unittest.main()
