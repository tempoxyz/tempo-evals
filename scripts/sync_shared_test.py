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

    def test_tempo_verifier_attachment_contains_only_selected_case(self) -> None:
        original_tasks_dir = sync_shared.TASKS_DIR
        with tempfile.TemporaryDirectory() as temporary_directory:
            tasks_dir = Path(temporary_directory)
            task_dir = tasks_dir / "transfer"
            task_dir.mkdir(parents=True)
            (task_dir / "task.toml").write_text(
                '[task]\nname = "tempo-v1/transfer"\n\n'
                '[environment.env]\nTEMPO_BENCH_CASE = "transfer-with-memo"\n'
            )

            sync_shared.TASKS_DIR = tasks_dir
            try:
                self.assertEqual(sync_shared.sync_tempo_verifiers(), 1)
            finally:
                sync_shared.TASKS_DIR = original_tasks_dir

            attachment = task_dir / "tests" / sync_shared.TEMPO_VERIFIER_ATTACHMENT
            self.assertTrue((attachment / "bin" / "tempo-bench-verify.js").is_file())
            self.assertTrue((attachment / "src" / "result.js").is_file())
            cases = sorted(
                path.name for path in (attachment / "src" / "cases").glob("*.js")
            )
            self.assertEqual(cases, ["index.js", "transfer-with-memo.js"])
            self.assertIn(
                '"transfer-with-memo": require("./transfer-with-memo")',
                (attachment / "src" / "cases" / "index.js").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
