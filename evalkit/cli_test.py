"""Tests for EvalKit's command-line dispatch and diagnostics."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evalkit.cli as cli


class CliTest(unittest.TestCase):
    def run_cli(self, *arguments: str) -> tuple[str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(sys, "argv", ["evalkit", *arguments]),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            cli.main()
        return stdout.getvalue(), stderr.getvalue()

    def test_build_dispatches_selected_suite_and_prints_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "output"
            with (
                patch.object(cli, "suite_names", return_value=("example",)),
                patch.object(
                    cli, "build", return_value=[output / "example/task"]
                ) as build,
            ):
                stdout, stderr = self.run_cli(
                    "build", "example", "--output-root", str(output)
                )

        self.assertEqual(stderr, "")
        self.assertEqual(stdout, f"{output / 'example/task'}\n")
        build.assert_called_once_with("example", output)

    def test_lint_dispatches_all_suites_and_loads_each_once_per_phase(self) -> None:
        suite = object()
        with (
            patch.object(cli, "suite_names", return_value=("first", "second")),
            patch.object(cli, "load_suite", return_value=suite) as load_suite,
            patch.object(cli, "validate") as validate,
            patch.object(cli, "lower_suite") as lower_suite,
        ):
            stdout, stderr = self.run_cli("lint")

        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "first: valid\nsecond: valid\n")
        self.assertEqual(load_suite.call_count, 4)
        self.assertEqual(validate.call_count, 2)
        self.assertEqual(lower_suite.call_count, 2)

    def test_diff_and_check_print_changed_and_clean_results(self) -> None:
        with (
            patch.object(cli, "suite_names", return_value=("example",)),
            patch.object(
                cli, "diff", return_value={"example/task": ["task.toml"]}
            ) as diff,
        ):
            stdout, _ = self.run_cli("diff", "example")
        self.assertEqual(stdout, "example/task: task.toml\n")
        diff.assert_called_once_with("example", Path("generated"))

        with (
            patch.object(cli, "suite_names", return_value=("example",)),
            patch.object(cli, "check", return_value={"example/task": []}) as check,
        ):
            stdout, _ = self.run_cli("check", "example")
        self.assertEqual(stdout, "No task-definition differences.\n")
        check.assert_called_once_with("example", Path("generated"))

    def test_new_writes_one_declaration_and_rejects_invalid_or_existing_targets(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "evalkit/suites").mkdir(parents=True)
            with patch.object(cli, "ROOT", root):
                stdout, _ = self.run_cli("new", "tempo-v1/example-task")
                module = root / "evalkit/suites/tempo_v1_example_task.py"
                self.assertEqual(stdout, f"{module}\n")
                self.assertIn('Task(name="tempo-v1/example-task")', module.read_text())
                with self.assertRaisesRegex(ValueError, "existing declaration"):
                    self.run_cli("new", "tempo-v1/example-task")
                with self.assertRaisesRegex(ValueError, "suite/name"):
                    self.run_cli("new", "invalid")
                with self.assertRaisesRegex(ValueError, "suite/name"):
                    self.run_cli("new", "../outside")
                with self.assertRaisesRegex(ValueError, "suite/name"):
                    self.run_cli("new", "tempo-v1/not.importable")

    def test_lock_and_explain_commands_validate_input_and_render_json(self) -> None:
        digest = "sha256:" + "a" * 64
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            lock_path = root / "evalkit.lock"
            with patch.object(cli, "update_lock", return_value=digest) as update:
                stdout, _ = self.run_cli(
                    "lock",
                    "--update",
                    "image=example/image:v1",
                    "--digest",
                    digest,
                    "--path",
                    str(lock_path),
                )
            self.assertEqual(stdout, f"{digest}\n")
            update.assert_called_once_with(lock_path, "example/image:v1", digest)

            task = root / "task"
            task.mkdir()
            (task / ".evalkit-manifest.json").write_text(json.dumps({"task": "x"}))
            stdout, _ = self.run_cli("explain", str(task))
            self.assertEqual(json.loads(stdout), {"task": "x"})

    def test_parser_reports_invalid_lock_and_missing_manifest(self) -> None:
        with self.assertRaises(SystemExit):
            self.run_cli("lock")
        with self.assertRaises(SystemExit):
            self.run_cli("lock", "--update", "example/image:v1")
        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            self.assertRaises(SystemExit),
        ):
            self.run_cli("explain", temporary_directory)

    def test_print_differences_ignores_empty_entries(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            cli._print_differences({"clean": [], "changed": ["task.toml", "README.md"]})
        self.assertEqual(output.getvalue(), "changed: task.toml, README.md\n")
