from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import prepare_docs_bundle
from scripts.prepare_docs_bundle import rewrite_canonical_docs_urls


class PrepareDocsBundleTest(unittest.TestCase):
    def test_prepared_bundle_requires_current_schema(self) -> None:
        lock = {"repo": "https://example.test/docs.git", "sha": "docs123"}

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(prepare_docs_bundle, "CACHE_ROOT", Path(directory)),
        ):
            public_dir = prepare_docs_bundle.public_dir(lock)
            public_dir.joinpath("developers").mkdir(parents=True)
            for name in ("llms.txt", "llms-full.txt", "index.html"):
                public_dir.joinpath("developers", name).write_text("docs\n")

            for schema_version, expected in (
                (prepare_docs_bundle.BUNDLE_SCHEMA_VERSION - 1, False),
                (prepare_docs_bundle.BUNDLE_SCHEMA_VERSION, True),
            ):
                with self.subTest(schema_version=schema_version):
                    prepare_docs_bundle.manifest_path(lock).write_text(
                        json.dumps(
                            {
                                "schemaVersion": schema_version,
                                "repo": lock["repo"],
                                "sha": lock["sha"],
                                "docCount": 1,
                            }
                        )
                    )
                    self.assertEqual(prepare_docs_bundle.is_prepared(lock), expected)

    def test_rewrites_only_canonical_documentation_urls(self) -> None:
        cases = {
            "https://tempo.xyz/developers/docs/quickstart/faucet": (
                "https://docs.tempo.xyz/developers/docs/quickstart/faucet"
            ),
            "https://tempo.xyz/developers/llms.txt": (
                "https://docs.tempo.xyz/developers/llms.txt"
            ),
            "https://tempo.xyz/developers/llms-full.txt": (
                "https://docs.tempo.xyz/developers/llms-full.txt"
            ),
            "https://tempo.xyz/developers/api/faucet": (
                "https://tempo.xyz/developers/api/faucet"
            ),
            "https://tempo.xyz/developers/docs-preview": (
                "https://tempo.xyz/developers/docs-preview"
            ),
            "https://tempo.xyz/SKILL.md": "https://tempo.xyz/SKILL.md",
        }

        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(rewrite_canonical_docs_urls(source), expected)


if __name__ == "__main__":
    unittest.main()
