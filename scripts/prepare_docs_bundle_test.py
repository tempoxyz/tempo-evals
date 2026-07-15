from __future__ import annotations

import unittest

from scripts.prepare_docs_bundle import rewrite_canonical_docs_urls


class PrepareDocsBundleTest(unittest.TestCase):
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
