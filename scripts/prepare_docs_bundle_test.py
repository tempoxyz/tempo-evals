from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import prepare_docs_bundle
from scripts.prepare_docs_bundle import (
    link_route_for,
    markdown_route_for,
    rewrite_canonical_docs_urls,
    route_for,
)

DOCS_SKILL = """---
name: tempo-docs
---

# Tempo Docs

All links below use the canonical docs mount at `https://tempo.xyz/developers`.

- [Get Started](https://tempo.xyz/developers/get-started.md)
- [Accounts](https://tempo.xyz/developers/docs/accounts.md)
- [Index](https://tempo.xyz/developers/llms.txt)
- Feedback: `https://tempo.xyz/developers/api/feedback`
"""

PRODUCT_NAVIGATION_CONFIG = """export default defineConfig({
  sidebar: (() => {
    const getStartedSidebar = [
      { text: 'Start building', link: '/get-started' },
      { text: 'Quickstart', link: '/get-started/quickstart' },
      { text: 'Viem', link: 'https://viem.sh/tempo' },
    ]
    const accountsSidebar = [{ text: 'Accounts', link: '/docs/accounts' }]
    return { '/docs': getStartedSidebar }
  })(),
  topNav: [{ text: 'Docs', link: '/' }],
})
"""

PUBLISHING_BUILD_CONFIG = (
    "await fs.copyFile(path.join(root, 'SKILL.md'), path.join(directory, 'SKILL.md'))\n"
)

# Each layout maps repository files to the bundle files they must produce, the
# bundle files that must not exist, and the llms.txt link order.
BUNDLE_LAYOUTS = {
    "product navigation": {
        "files": {
            "SKILL.md": DOCS_SKILL,
            "vite.config.ts": PUBLISHING_BUILD_CONFIG,
            "vocs.config.ts": PRODUCT_NAVIGATION_CONFIG,
            "src/pages/index.mdx": "---\ntitle: Documentation\n---\n\n# Home\n",
            "src/pages/get-started.mdx": "---\ntitle: Build on Tempo\n---\n\n# Build\n",
            "src/pages/get-started/quickstart.mdx": "# Quickstart\n",
            "src/pages/docs/accounts.mdx": "# Accounts\n",
            "src/pages/_layout.tsx": "export {}\n",
        },
        "present": [
            "developers/SKILL.md",
            "developers/index.md",
            "developers/docs.md",
            "developers/get-started.md",
            "developers/get-started/quickstart.md",
            "developers/docs/accounts.md",
        ],
        "absent": [],
        "links": [
            "/get-started",
            "/get-started/quickstart",
            "/docs/accounts",
            "/",
        ],
        "skill": True,
    },
    "docs landing with an unpublished skill": {
        "files": {
            "SKILL.md": DOCS_SKILL,
            "vite.config.ts": "export default defineConfig({})\n",
            "src/pages/docs/index.mdx": "# Docs\n",
            "src/pages/docs/guide/index.mdx": "# Guides\n",
        },
        "present": [
            "developers/docs.md",
            "developers/docs/guide.md",
        ],
        "absent": [
            "developers/SKILL.md",
            "developers/index.md",
        ],
        "links": ["/docs/", "/docs/guide/"],
        "skill": False,
    },
}


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
        docs = "https://docs.tempo.xyz/developers"
        cases = {
            "https://tempo.xyz/developers/docs/quickstart/faucet": (
                f"{docs}/docs/quickstart/faucet"
            ),
            "https://tempo.xyz/developers/docs.md": f"{docs}/docs.md",
            "https://tempo.xyz/developers/llms.txt": f"{docs}/llms.txt",
            "https://tempo.xyz/developers/llms-full.txt": f"{docs}/llms-full.txt",
            "https://tempo.xyz/developers/SKILL.md": f"{docs}/SKILL.md",
            "https://tempo.xyz/developers/skill.md": f"{docs}/skill.md",
            "https://tempo.xyz/developers/index.md": f"{docs}/index.md",
            "https://tempo.xyz/developers/get-started.md": f"{docs}/get-started.md",
            "https://tempo.xyz/developers/get-started/quickstart": (
                f"{docs}/get-started/quickstart"
            ),
            "https://tempo.xyz/developers": docs,
            "https://tempo.xyz/developers/": f"{docs}/",
            "mount at `https://tempo.xyz/developers`.": f"mount at `{docs}`.",
            "[Docs](https://tempo.xyz/developers)": f"[Docs]({docs})",
            "https://tempo.xyz/developers/api/faucet": (
                "https://tempo.xyz/developers/api/faucet"
            ),
            "`https://tempo.xyz/developers/api/feedback`": (
                "`https://tempo.xyz/developers/api/feedback`"
            ),
            "https://tempo.xyz/developers/docs-preview": (
                "https://tempo.xyz/developers/docs-preview"
            ),
            "https://tempo.xyz/developers/get-started-now": (
                "https://tempo.xyz/developers/get-started-now"
            ),
            "https://tempo.xyz/developersx": "https://tempo.xyz/developersx",
            "https://tempo.xyz/SKILL.md": "https://tempo.xyz/SKILL.md",
            "https://tempo.xyz/install": "https://tempo.xyz/install",
        }

        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(rewrite_canonical_docs_urls(source), expected)

    def test_routes_follow_the_production_docs_mount(self) -> None:
        cases = {
            "index.mdx": ("/", "/", "/developers/index.md"),
            "get-started.mdx": (
                "/get-started",
                "/get-started",
                "/developers/get-started.md",
            ),
            "get-started/quickstart.mdx": (
                "/get-started/quickstart",
                "/get-started/quickstart",
                "/developers/get-started/quickstart.md",
            ),
            "docs/index.mdx": ("/docs", "/docs/", "/developers/docs.md"),
            "docs/cli/index.mdx": (
                "/docs/cli",
                "/docs/cli/",
                "/developers/docs/cli.md",
            ),
            "docs/reindex.md": (
                "/docs/reindex",
                "/docs/reindex",
                "/developers/docs/reindex.md",
            ),
        }

        for relative_path, expected in cases.items():
            with self.subTest(relative_path=relative_path):
                route = route_for(Path(relative_path))
                self.assertEqual(
                    (
                        route,
                        link_route_for(Path(relative_path)),
                        markdown_route_for(route),
                    ),
                    expected,
                )

    def test_build_bundle_exports_agent_entry_points(self) -> None:
        lock = {"repo": "https://example.test/docs.git", "sha": "docs123"}

        for name, layout in BUNDLE_LAYOUTS.items():
            with (
                self.subTest(layout=name),
                tempfile.TemporaryDirectory() as directory,
                patch.object(prepare_docs_bundle, "CACHE_ROOT", Path(directory)),
            ):
                repo = prepare_docs_bundle.repo_dir(lock)
                for relative_path, content in layout["files"].items():
                    prepare_docs_bundle.write_file(repo / relative_path, content)

                prepare_docs_bundle.build_bundle(lock)

                public = prepare_docs_bundle.public_dir(lock)
                for relative_path in layout["present"]:
                    self.assertTrue((public / relative_path).is_file(), relative_path)
                for relative_path in layout["absent"]:
                    self.assertFalse((public / relative_path).exists(), relative_path)

                llms = (public / "developers" / "llms.txt").read_text()
                links = [
                    line.split("](", 1)[1].split(")", 1)[0]
                    for line in llms.splitlines()
                    if line.startswith("- [")
                ]
                self.assertEqual(links, layout["links"])
                self.assertEqual(
                    "[Docs skill](/developers/SKILL.md)" in llms, layout["skill"]
                )

                manifest = json.loads((public / "manifest.json").read_text())
                self.assertEqual(manifest["docCount"], len(layout["links"]))
                self.assertEqual(
                    manifest["routes"].get("skill"),
                    "/developers/SKILL.md" if layout["skill"] else None,
                )
                self.assertTrue(prepare_docs_bundle.is_prepared(lock))

    def test_bundled_skill_points_at_the_pinned_docs_host(self) -> None:
        lock = {"repo": "https://example.test/docs.git", "sha": "docs123"}

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(prepare_docs_bundle, "CACHE_ROOT", Path(directory)),
        ):
            repo = prepare_docs_bundle.repo_dir(lock)
            for relative_path, content in BUNDLE_LAYOUTS["product navigation"][
                "files"
            ].items():
                prepare_docs_bundle.write_file(repo / relative_path, content)

            prepare_docs_bundle.build_bundle(lock)

            skill = (
                prepare_docs_bundle.public_dir(lock) / "developers" / "SKILL.md"
            ).read_text()
            self.assertTrue(skill.startswith("---\nname: tempo-docs\n---\n"))
            self.assertNotIn("https://tempo.xyz/developers/get-started", skill)
            self.assertIn("https://docs.tempo.xyz/developers/get-started.md", skill)
            self.assertIn("https://docs.tempo.xyz/developers/docs/accounts.md", skill)
            self.assertIn("`https://docs.tempo.xyz/developers`", skill)
            self.assertIn("`https://tempo.xyz/developers/api/feedback`", skill)


if __name__ == "__main__":
    unittest.main()
