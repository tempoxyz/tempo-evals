from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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

    def test_tempo_verifier_digest_is_pinned_into_each_task(self) -> None:
        original_tasks_dir = sync_shared.TASKS_DIR
        with tempfile.TemporaryDirectory() as temporary_directory:
            tasks_dir = Path(temporary_directory)
            for directory in ("alpha", "beta"):
                task_dir = tasks_dir / directory
                task_dir.mkdir(parents=True)
                (task_dir / "task.toml").write_text(
                    f'[task]\nname = "tempo-v1/{directory}"\n'
                )

            sync_shared.TASKS_DIR = tasks_dir
            try:
                with patch.object(
                    sync_shared,
                    "tempo_verifier_digest",
                    return_value="sha256:" + "a" * 64,
                ):
                    self.assertEqual(sync_shared.sync_tempo_verifier_digests(), 2)
            finally:
                sync_shared.TASKS_DIR = original_tasks_dir

            for directory in ("alpha", "beta"):
                digest_file = (
                    tasks_dir / directory / sync_shared.TEMPO_VERIFIER_DIGEST_FILE
                )
                self.assertEqual(digest_file.read_text(), "sha256:" + "a" * 64 + "\n")


if __name__ == "__main__":
    unittest.main()
