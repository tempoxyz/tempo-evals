"""Tests for image-lock persistence and validation."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evalkit.api import ImageRef
from evalkit.lock import inspect_digest, load, resolve, update


class LockTest(unittest.TestCase):
    def test_load_handles_missing_and_invalid_lock_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "evalkit.lock"
            self.assertEqual(load(path), {})
            path.write_text("images = []\n")
            with self.assertRaisesRegex(ValueError, "Invalid image lock"):
                load(path)

    def test_resolve_rejects_missing_and_malformed_digests(self) -> None:
        image = ImageRef("example/image", "v1")
        with self.assertRaisesRegex(ValueError, "not locked"):
            resolve(image, {})
        with self.assertRaisesRegex(ValueError, "Invalid digest"):
            resolve(image, {image.reference: "not-a-digest"})
        with self.assertRaisesRegex(ValueError, "Invalid digest"):
            resolve(image, {image.reference: "sha256:not-a-real-digest"})

    @patch("evalkit.lock.subprocess.run")
    def test_inspect_digest_rejects_output_without_a_digest(self, run: object) -> None:
        run.return_value.stdout = "Name: example/image:v1\n"
        with self.assertRaisesRegex(ValueError, "did not return a digest"):
            inspect_digest("example/image:v1")

    @patch("evalkit.lock.inspect_digest")
    def test_update_inspects_missing_digest_and_rejects_invalid_values(
        self, inspect: object
    ) -> None:
        digest = "sha256:" + "e" * 64
        inspect.return_value = digest
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "evalkit.lock"
            self.assertEqual(update(path, "example/image:v1"), digest)
            self.assertEqual(load(path), {"example/image:v1": digest})
            with self.assertRaisesRegex(ValueError, "Invalid digest"):
                update(path, "example/image:v1", "bad")
            with self.assertRaisesRegex(ValueError, "Invalid digest"):
                update(path, "example/image:v1", "sha256:too-short")

    @patch("evalkit.lock.subprocess.run")
    def test_inspect_digest_surfaces_docker_failures(self, run: object) -> None:
        run.side_effect = subprocess.CalledProcessError(1, "docker")
        with self.assertRaises(subprocess.CalledProcessError):
            inspect_digest("example/image:v1")
