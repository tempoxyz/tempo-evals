"""Regression tests for deterministic evalkit compilation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harbor.publisher.packager import Packager

from evalkit.api import (
    AdapterContract,
    Bake,
    DockerBuild,
    Environment,
    ImageRef,
    SharedVerifier,
    Suite,
    Task,
    VerifierUse,
    bake,
    copy,
    env,
    instruction_fragment,
    override,
    runtime_service,
)
from evalkit.api import (
    Policy as ApiPolicy,
)
from evalkit.compiler import build, check, diff, load_suite, lower_suite, suite_names
from evalkit.harbor_compat import content_hash
from evalkit.lock import inspect_digest, load, update


def Policy(**kwargs: object) -> ApiPolicy:
    """Allow focused compiler tests to exercise incomplete declarations."""
    return ApiPolicy(allow_incomplete_tasks=True, **kwargs)


class BuildTest(unittest.TestCase):
    def test_all_existing_suites_are_registered(self) -> None:
        self.assertEqual(suite_names(), ("mpp", "tempo-mcp-v1", "tempo-v1"))
        self.assertEqual(len(load_suite("mpp").tasks), 9)
        self.assertEqual(len(load_suite("tempo-mcp-v1").tasks), 12)
        self.assertEqual(len(load_suite("tempo-v1").tasks), 9)

    def test_build_preserves_harbor_content_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory) / "generated"
            rendered = next(
                path
                for path in build("tempo-v1", output_root)
                if path.name == "faucet-funded-transfer"
            )
            second_output_root = Path(temporary_directory) / "second-generated"
            second_rendered = next(
                path
                for path in build("tempo-v1", second_output_root)
                if path.name == "faucet-funded-transfer"
            )
            source = Path("tasks/tempo-v1/faucet-funded-transfer")

            self.assertEqual(
                content_hash(source), Packager.compute_content_hash(source)[0]
            )
            self.assertEqual(
                content_hash(rendered), Packager.compute_content_hash(rendered)[0]
            )
            self.assertEqual(content_hash(source), content_hash(rendered))
            self.assertEqual(
                (rendered / ".evalkit-manifest.json").read_bytes(),
                (second_rendered / ".evalkit-manifest.json").read_bytes(),
            )
            differences = diff("tempo-v1", output_root)
            self.assertEqual(differences["tempo-v1/faucet-funded-transfer"], [])
            self.assertTrue(all(not paths for paths in differences.values()))
            self.assertEqual(check("tempo-v1", output_root), differences)

    def test_lowering_renders_environment_and_services(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source.txt"
            source.write_text("source\n")
            lock_path = root / "evalkit.lock"
            update(lock_path, "example/service:v1", "sha256:" + "a" * 64)
            task = Task(
                name="example/task",
                copies=(copy(source, "solution/source.txt"),),
                environment=Environment(
                    agent=DockerBuild(ImageRef("example/service", "v1")),
                    verifier=DockerBuild(ImageRef("example/service", "v1")),
                    variables=(
                        env("ONE", default="1"),
                        env("TWO", required=True),
                        env("OPTIONAL", required=False),
                    ),
                    services=(
                        runtime_service("docs", ImageRef("example/service", "v1")),
                    ),
                ),
                instruction=instruction_fragment("# Example", "Build it."),
                extra_config={
                    "metadata": {"category": "integration"},
                    "task": {
                        "description": "Example task",
                        "name": "other/task",
                    },
                },
            )
            suite = Suite("example", (task,), policy=Policy(require_image_locks=True))

            ir = lower_suite(suite, lock_path)
            assets = {
                asset.destination.as_posix(): asset.source.read_bytes()
                for asset in ir.tasks[0].assets
            }

            self.assertIn("environment/Dockerfile", assets)
            self.assertIn("environment/compose.yaml", assets)
            self.assertIn(b'ONE = "1"', assets["task.toml"])
            self.assertIn(b'TWO = ""', assets["task.toml"])
            self.assertNotIn(b"OPTIONAL", assets["task.toml"])
            self.assertIn(b'category = "integration"', assets["task.toml"])
            self.assertIn(b'description = "Example task"', assets["task.toml"])
            self.assertIn(b'name = "example/task"', assets["task.toml"])
            self.assertNotIn(b'name = "other/task"', assets["task.toml"])
            self.assertIn(b"# Example", assets["instruction.md"])
            self.assertEqual(
                ir.tasks[0].resolved_images[0].digest, "sha256:" + "a" * 64
            )

    def test_bake_uses_locked_image_and_copies_build_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            payload = root / "payload.txt"
            payload.write_text("payload\n")
            lock_path = root / "evalkit.lock"
            update(lock_path, "example/image:v1", "sha256:" + "c" * 64)
            build_spec: Bake = bake(payload, "/opt/payload.txt", into="agent")
            task = Task(
                "example/task",
                environment=Environment(
                    agent=DockerBuild(ImageRef("example/image", "v1"), (build_spec,)),
                ),
            )
            ir = lower_suite(
                Suite("example", (task,), policy=Policy()), lock_path
            ).tasks[0]
            assets = {
                asset.destination.as_posix(): asset.source.read_bytes()
                for asset in ir.assets
            }
            self.assertEqual(
                assets["environment/baked/agent/opt/payload.txt"], b"payload\n"
            )
            self.assertIn(
                b"FROM example/image:v1@sha256:", assets["environment/Dockerfile"]
            )

    def test_missing_image_lock_is_rejected(self) -> None:
        task = Task(
            "example/task",
            environment=Environment(agent=DockerBuild(ImageRef("example/image", "v1"))),
        )
        with self.assertRaisesRegex(ValueError, "Image is not locked"):
            lower_suite(Suite("example", (task,), policy=Policy()))

    def test_aliases_are_preserved_and_unique(self) -> None:
        task = Task("example/task", aliases=("example/old-task",))
        ir = lower_suite(
            Suite("example", (task,), policy=Policy(require_image_locks=False))
        )
        self.assertEqual(ir.tasks[0].aliases, ("example/old-task",))
        duplicate = Task("example/second", aliases=("example/old-task",))
        with self.assertRaisesRegex(ValueError, "duplicate task names or aliases"):
            lower_suite(
                Suite(
                    "example",
                    (task, duplicate),
                    policy=Policy(require_image_locks=False),
                )
            )

    def test_collision_requires_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            first = root / "first"
            second = root / "second"
            first.write_text("first")
            second.write_text("second")
            task = Task(
                "example/task",
                copies=(
                    copy(first, "solution/file.txt"),
                    copy(second, "solution/file.txt"),
                ),
            )
            with self.assertRaisesRegex(ValueError, "use override"):
                lower_suite(
                    Suite("example", (task,), policy=Policy(require_image_locks=False))
                )

            overridden = Task(
                "example/task",
                copies=(
                    copy(first, "solution/file.txt"),
                    copy(second, "solution/file.txt"),
                ),
                overrides=(
                    override("solution/file.txt", reason="task-specific source"),
                ),
            )
            ir = lower_suite(
                Suite(
                    "example", (overridden,), policy=Policy(require_image_locks=False)
                )
            )
            asset = next(
                asset
                for asset in ir.tasks[0].assets
                if asset.destination.name == "file.txt"
            )
            self.assertEqual(asset.source.read_bytes(), b"second")
            self.assertEqual(asset.provenance.override_reason, "task-specific source")

    def test_verifier_contract_uses_ast_without_importing_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            verifier = root / "verifier"
            verifier.mkdir()
            adapter = root / "adapter.py"
            adapter.write_text("def check():\n    return True\n")
            task = Task(
                "example/task",
                verifiers=(
                    VerifierUse(
                        SharedVerifier(
                            "shared",
                            verifier,
                            AdapterContract(Path("adapter.py"), ("check",)),
                        ),
                        adapter,
                    ),
                ),
            )
            lower_suite(
                Suite("example", (task,), policy=Policy(require_image_locks=False))
            )

            invalid = Task(
                "example/task",
                verifiers=(
                    VerifierUse(
                        SharedVerifier(
                            "shared",
                            verifier,
                            AdapterContract(Path("adapter.py"), ("missing",)),
                        ),
                        adapter,
                    ),
                ),
            )
            with self.assertRaisesRegex(ValueError, "lacks missing"):
                lower_suite(
                    Suite(
                        "example", (invalid,), policy=Policy(require_image_locks=False)
                    )
                )

    def test_lock_update_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            lock_path = Path(temporary_directory) / "evalkit.lock"
            digest = "sha256:" + "b" * 64
            self.assertEqual(update(lock_path, "example/image:v1", digest), digest)
            self.assertEqual(load(lock_path), {"example/image:v1": digest})

    @patch("evalkit.lock.subprocess.run")
    def test_lock_inspection_parses_registry_digest(self, run: object) -> None:
        digest = "sha256:" + "d" * 64
        run.return_value.stdout = f"Name: example/image:v1\nDigest: {digest}\n"
        self.assertEqual(inspect_digest("example/image:v1"), digest)
