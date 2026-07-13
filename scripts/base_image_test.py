from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.base_image import source_hash, source_image_ref
from scripts.run_benchmark import base_image_ref, override_staged_base_image


class BaseImageTest(unittest.TestCase):
    def test_base_image_caches_verifier_dependencies_without_source(self) -> None:
        dockerfile = (
            Path(__file__).parents[1]
            / "shared"
            / "global"
            / "docker"
            / "base"
            / "Dockerfile"
        ).read_text()

        self.assertIn("/opt/tempo-bench-verifier-deps", dockerfile)
        self.assertNotIn("COPY shared/tempo/verifier /opt", dockerfile)
        self.assertNotIn("/opt/tempo-bench/verifier", dockerfile)

    def test_source_image_ref_uses_a_stable_content_hash(self) -> None:
        self.assertRegex(source_hash(), r"^[0-9a-f]{16}$")
        self.assertEqual(
            source_image_ref(),
            f"{base_image_ref().rsplit(':', 1)[0]}:source-{source_hash()}",
        )

    def test_override_staged_base_image_uses_the_published_ref(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dockerfile = (
                Path(directory)
                / "tasks"
                / "tempo-v1"
                / "task"
                / "environment"
                / "Dockerfile"
            )
            dockerfile.parent.mkdir(parents=True)
            dockerfile.write_text(f"FROM {base_image_ref()}\n")

            override_staged_base_image(Path(directory), "ghcr.io/test/base@sha256:abc")

            self.assertEqual(
                dockerfile.read_text(), "FROM ghcr.io/test/base@sha256:abc\n"
            )
