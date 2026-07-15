from __future__ import annotations

import tempfile
import unittest
from os import chmod
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from scripts.images import (
    INPUTS,
    configured_image_ref,
    image_repository,
    immutable_ref,
    source_entry,
    source_hash,
    source_image_ref,
    source_image_tag,
)
from scripts.run_benchmark import image_ref, override_staged_images


class ImagesTest(unittest.TestCase):
    def test_source_tags_share_a_stable_pair_hash(self) -> None:
        self.assertRegex(source_hash(), r"^[0-9a-f]{64}$")
        for image in ("agent", "verifier"):
            self.assertEqual(
                source_image_tag(image),
                f"{image_repository()}:{image}-source-{source_hash()}",
            )
            self.assertEqual(configured_image_ref(image), source_image_tag(image))

    def test_hash_inputs_include_build_configuration(self) -> None:
        for path in (
            Path(".dockerignore"),
            Path(".github/workflows/build-images.yml"),
            Path("scripts/images.py"),
        ):
            self.assertIn(path, INPUTS)

    def test_source_entry_hashes_mode_and_symlink_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            regular = root / "regular"
            regular.write_text("content")
            chmod(regular, 0o644)
            self.assertEqual(source_entry(regular), ("100644", b"content"))
            chmod(regular, 0o755)
            self.assertEqual(source_entry(regular), ("100755", b"content"))

            link = root / "link"
            link.symlink_to("first-target")
            self.assertEqual(source_entry(link), ("120000", b"first-target"))

    @patch("scripts.images.subprocess.run")
    def test_immutable_ref_resolves_the_registry_digest(self, run) -> None:
        run.return_value = CompletedProcess(
            [], 0, stdout=f"sha256:{'a' * 64}\n", stderr=""
        )

        self.assertEqual(
            immutable_ref("ghcr.io/tempoxyz/tempo-bench-base:agent-source-test"),
            f"ghcr.io/tempoxyz/tempo-bench-base@sha256:{'a' * 64}",
        )

    @patch("scripts.images.immutable_ref")
    def test_source_ref_requires_the_complete_pair(self, resolve) -> None:
        resolve.side_effect = ["agent@sha256:a", RuntimeError("missing verifier")]

        with self.assertRaisesRegex(RuntimeError, "missing verifier"):
            source_image_ref("agent")
        self.assertEqual(resolve.call_count, 2)

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
