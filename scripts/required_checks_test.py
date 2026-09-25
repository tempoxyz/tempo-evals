from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


class RequiredChecksTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = yaml.load(
            (ROOT / ".github/workflows/build-images.yml").read_text(),
            Loader=yaml.BaseLoader,
        )
        self.jobs = self.workflow["jobs"]

    def run_step(self, script: str, env: dict[str, str]) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            result = subprocess.run(
                ["bash", "-c", script],
                env={**os.environ, **env, "GITHUB_OUTPUT": str(output)},
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode, output.read_text() if output.exists() else ""

    def detect(self, pages: list, **overrides: str) -> tuple[int, str]:
        script = next(
            step["run"]
            for step in self.jobs["changes"]["steps"]
            if step.get("id") == "detect"
        )
        mock = """
        gh() {
          if [ "$API_FAIL" = true ]; then return 1; fi
          case "$*" in
            */files*) printf '%s' "$PAGES" ;;
            *) printf '%s' "$COUNT" ;;
          esac
        }
        """
        return self.run_step(
            mock + script,
            {
                "EVENT_NAME": "pull_request",
                "REPO": "example/repo",
                "PR_NUMBER": "1",
                "COUNT": "1",
                "PAGES": json.dumps(pages),
                "API_FAIL": "false",
                **overrides,
            },
        )

    def test_pr_workflows_are_not_path_filtered(self) -> None:
        self.assertFalse(self.workflow["on"]["pull_request"])
        self.assertTrue(self.workflow["on"]["push"]["paths"])
        static = yaml.load(
            (ROOT / ".github/workflows/static-checks.yml").read_text(),
            Loader=yaml.BaseLoader,
        )
        self.assertNotIn("paths", static["on"]["pull_request_target"])
        gate = self.jobs["build-and-push"]
        self.assertEqual(gate["if"], "always()")
        self.assertEqual(gate["needs"], ["changes", "validate", "publish"])
        for job in ("validate", "publish"):
            self.assertEqual(self.jobs[job]["needs"], "changes")
            self.assertIn(
                "needs.changes.outputs.images == 'true'", self.jobs[job]["if"]
            )

    def test_unrelated_files_do_not_build(self) -> None:
        self.assertEqual(
            self.detect([[{"filename": ".github/dependabot.yml"}]]),
            (0, "images=false\n"),
        )

    def test_all_existing_image_filters_still_build(self) -> None:
        for pattern in self.workflow["on"]["push"]["paths"]:
            with self.subTest(pattern=pattern):
                path = pattern.replace("**", "nested/input")
                self.assertEqual(
                    self.detect([[{"filename": path}]]), (0, "images=true\n")
                )

    def test_renames_and_later_pages_build(self) -> None:
        self.assertEqual(
            self.detect(
                [
                    [{"filename": "README.md"}],
                    [
                        {
                            "filename": "archive/file",
                            "previous_filename": "scripts/images.py",
                        }
                    ],
                ]
            ),
            (0, "images=true\n"),
        )

    def test_large_prs_and_pushes_build_without_file_listing(self) -> None:
        self.assertEqual(self.detect([], COUNT="3000"), (0, "images=true\n"))
        self.assertEqual(
            self.detect([], EVENT_NAME="push", API_FAIL="true"), (0, "images=true\n")
        )

    def test_api_failure_is_not_treated_as_no_changes(self) -> None:
        status, output = self.detect([], API_FAIL="true")
        self.assertNotEqual(status, 0)
        self.assertEqual(output, "")

    def test_required_gate_propagates_failures_and_cancellations(self) -> None:
        script = self.jobs["build-and-push"]["steps"][-1]["run"]
        defaults = {
            "CHANGES_RESULT": "success",
            "IMAGES_CHANGED": "false",
            "VALIDATE_RESULT": "skipped",
            "PUBLISH_RESULT": "skipped",
            "IS_FORK": "false",
        }
        cases = [
            ({}, True),
            ({"CHANGES_RESULT": "failure"}, False),
            ({"CHANGES_RESULT": "cancelled"}, False),
            ({"IMAGES_CHANGED": ""}, False),
            ({"IMAGES_CHANGED": "true", "PUBLISH_RESULT": "success"}, True),
            ({"IMAGES_CHANGED": "true", "PUBLISH_RESULT": "failure"}, False),
            ({"IMAGES_CHANGED": "true", "PUBLISH_RESULT": "cancelled"}, False),
            ({"IMAGES_CHANGED": "true"}, False),
        ]
        for result in ("success", "failure", "cancelled", "skipped"):
            cases.append(
                (
                    {
                        "IMAGES_CHANGED": "true",
                        "IS_FORK": "true",
                        "VALIDATE_RESULT": result,
                    },
                    result == "success",
                )
            )
        for overrides, succeeds in cases:
            with self.subTest(overrides=overrides):
                status, _ = self.run_step(script, {**defaults, **overrides})
                self.assertEqual(status == 0, succeeds)


if __name__ == "__main__":
    unittest.main()
