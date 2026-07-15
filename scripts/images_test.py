from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.images import INPUTS, image_repository, source_hash, source_image_ref
from scripts.run_benchmark import image_ref, override_staged_images


class ImagesTest(unittest.TestCase):
    def test_source_refs_share_a_stable_content_tag(self) -> None:
        self.assertRegex(source_hash(), r"^[0-9a-f]{16}$")
        for image in ("agent", "verifier"):
            self.assertEqual(
                source_image_ref(image),
                f"{image_repository(image)}:source-{source_hash()}",
            )

    def test_hash_inputs_include_the_dockerignore(self) -> None:
        self.assertIn(Path(".dockerignore"), INPUTS)

    def test_override_staged_images_uses_published_refs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            task = Path(directory) / "tasks" / "tempo-v1" / "task"
            task.mkdir(parents=True)
            (task / "task.toml").write_text("")
            dockerfiles = {
                "agent": task / "environment" / "Dockerfile",
                "verifier": task / "tests" / "Dockerfile",
            }
            for image, dockerfile in dockerfiles.items():
                dockerfile.parent.mkdir(parents=True)
                dockerfile.write_text(f"FROM {image_ref(image)}\n")

            override_staged_images(
                Path(directory),
                {
                    "agent": "ghcr.io/test/agent@sha256:abc",
                    "verifier": "ghcr.io/test/verifier@sha256:def",
                },
            )

            self.assertEqual(
                dockerfiles["agent"].read_text(),
                "FROM ghcr.io/test/agent@sha256:abc\n",
            )
            self.assertEqual(
                dockerfiles["verifier"].read_text(),
                "FROM ghcr.io/test/verifier@sha256:def\n",
            )
