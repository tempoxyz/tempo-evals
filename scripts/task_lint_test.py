from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.task_lint import SUITES, lint
from scripts.task_new import create_task


class TaskLintTest(unittest.TestCase):
    def test_new_tasks_pass_lint_for_every_suite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for suite in SUITES:
                (root / suite.path).mkdir(parents=True)
            for suite_id in ("tempo", "mpp", "tempo-mcp"):
                create_task(root, suite_id, f"{suite_id}-task")

            self.assertEqual(lint(root), [])

    def test_lint_rejects_missing_and_duplicate_canaries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for suite in SUITES:
                (root / suite.path).mkdir(parents=True)
            first = create_task(root, "tempo", "first")
            second = create_task(root, "tempo", "second")
            first_instruction = first / "instruction.md"
            canary = first_instruction.read_text().splitlines()[0]
            (second / "instruction.md").write_text(
                canary + "\n# Second\nWrite /app/out.json.\n"
            )

            errors = lint(root)

            self.assertTrue(any("duplicate canary" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
