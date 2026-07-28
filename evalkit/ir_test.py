"""Tests for immutable EvalKit intermediate-representation values."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evalkit.ir import SourceRef


class IrTest(unittest.TestCase):
    def test_source_ref_reads_content_and_files_and_rejects_empty_references(
        self,
    ) -> None:
        self.assertEqual(SourceRef(content=b"rendered").read_bytes(), b"rendered")
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source.txt"
            source.write_bytes(b"file")
            self.assertEqual(SourceRef(path=source).read_bytes(), b"file")
        with self.assertRaisesRegex(ValueError, "neither path nor content"):
            SourceRef().read_bytes()
