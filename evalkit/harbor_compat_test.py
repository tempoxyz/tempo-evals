"""Tests for Harbor-compatible file selection and hashing."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evalkit.harbor_compat import collect_files, content_hash, file_hash


class HarborCompatTest(unittest.TestCase):
    def test_collect_files_applies_default_and_task_specific_ignores(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            task = Path(temporary_directory)
            (task / "task.toml").write_text("[task]\nname = 'example/task'\n")
            (task / "instruction.md").write_text("do it\n")
            environment = task / "environment"
            environment.mkdir()
            (environment / "Dockerfile").write_text("FROM scratch\n")
            (environment / "ignored.pyc").write_bytes(b"ignored")
            (task / ".gitignore").write_text("environment/Dockerfile\n")

            files = collect_files(task)

            self.assertEqual(
                [path.relative_to(task.resolve()).as_posix() for path in files],
                ["environment/ignored.pyc", "instruction.md", "task.toml"],
            )
            (task / ".gitignore").unlink()
            self.assertNotIn(
                task.resolve() / "environment/ignored.pyc", collect_files(task)
            )
            self.assertEqual(
                file_hash(task / "instruction.md"), file_hash(task / "instruction.md")
            )
            original = content_hash(task)
            (task / "README.md").write_text("details\n")
            self.assertNotEqual(content_hash(task), original)
