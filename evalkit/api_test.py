"""Tests for EvalKit's small public declaration API."""

from __future__ import annotations

import unittest
from pathlib import Path, PurePosixPath

from evalkit.api import (
    ImageRef,
    bake,
    copy,
    env,
    fixture,
    instruction_fragment,
    override,
    path,
    runtime_mcp,
    runtime_service,
)


class ApiTest(unittest.TestCase):
    def test_helpers_normalize_public_declarations(self) -> None:
        image = ImageRef("example/service", "v1")
        copied = copy("input.txt", "solution/input.txt")
        baked = bake("input.txt", "/opt/input.txt", into="agent", mode=0o755)

        self.assertEqual(
            path("solution/input.txt"), PurePosixPath("solution/input.txt")
        )
        self.assertEqual(image.reference, "example/service:v1")
        self.assertEqual(copied.source, Path("input.txt"))
        self.assertEqual(baked.destination, PurePosixPath("/opt/input.txt"))
        self.assertEqual(
            override(copied, reason="replace input").destination, copied.destination
        )
        self.assertEqual(
            override(baked, reason="replace bake").destination, baked.destination
        )
        self.assertEqual(fixture("sample.json", "sample").schema, None)
        self.assertEqual(env("TOKEN", required=False).name, "TOKEN")
        self.assertEqual(runtime_service("api", image).env, {})
        self.assertEqual(runtime_mcp("mcp", "https://example.test", "default").env, {})
        self.assertEqual(
            instruction_fragment("\n# Title\n", "", " Body ").content,
            "# Title\n\nBody\n",
        )

    def test_paths_and_overrides_reject_escapes_and_missing_rationale(self) -> None:
        for value in ("/absolute", "../escape", "solution/../../escape"):
            with (
                self.subTest(value=value),
                self.assertRaisesRegex(ValueError, "relative"),
            ):
                path(value)
        with self.assertRaisesRegex(ValueError, "must not escape"):
            bake("input", "../escape", into="agent")
        with self.assertRaisesRegex(ValueError, "requires a reason"):
            override("solution/file", reason="")
