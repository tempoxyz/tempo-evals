from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.prepare_mpp_docs_bundle import build_bundle


class PrepareMppDocsBundleTest(unittest.TestCase):
    def test_build_bundle_copies_dist_public_and_writes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "mpp"
            public = source / "dist" / "public"
            markdown = public / "assets" / "md" / "quickstart" / "server.md"
            markdown.parent.mkdir(parents=True)
            markdown.write_text("# Server quickstart\n")
            (public / "llms.txt").write_text("# MPP\n")
            (public / "llms-full.txt").write_text("# Full MPP docs\n")

            output = root / "bundle"
            build_bundle(source, output)

            self.assertEqual(
                (output / "assets" / "md" / "quickstart" / "server.md").read_text(),
                "# Server quickstart\n",
            )
            self.assertEqual(
                (output / "llms-full.txt").read_text(), "# Full MPP docs\n"
            )
            self.assertTrue((output / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
