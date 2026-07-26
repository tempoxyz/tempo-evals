"""Focused behavior and failure-path tests for the EvalKit compiler."""

from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest.mock import patch

from evalkit.api import (
    AdapterContract,
    Case,
    DockerBuild,
    Environment,
    Fixture,
    ImageRef,
    Policy,
    SharedVerifier,
    Solution,
    Suite,
    Task,
    VerifierUse,
    bake,
    copy,
    env,
    fixture,
    instruction_fragment,
    runtime_service,
)
from evalkit.compiler.build import (
    MANIFEST,
    _write_asset,
    check,
    destination,
    emit,
    load_suite,
    lower_suite,
    manifest,
    task_differences,
    task_slug,
    validate,
)
from evalkit.ir import Asset, Provenance, SourceRef, SuiteIR, TaskIR


class BuildEdgeTest(unittest.TestCase):
    def test_validate_rejects_invalid_suite_declarations(self) -> None:
        with self.assertRaisesRegex(ValueError, "has no tasks"):
            validate(Suite("example", ()))

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            missing = root / "missing.toml"
            with self.assertRaisesRegex(ValueError, "Missing dataset"):
                validate(Suite("example", (Task("example/task"),), missing))

            source = root / "source"
            source.mkdir()
            with self.assertRaisesRegex(ValueError, "Missing task.toml"):
                validate(Suite("example", (Task("example/task", source=source),)))
            with self.assertRaisesRegex(ValueError, "Missing task source"):
                validate(
                    Suite("example", (Task("example/task", source=root / "nope"),))
                )
            with self.assertRaisesRegex(ValueError, "Suite names"):
                validate(Suite("../escape", (Task("example/task"),)))

        task = Task("example/task")
        duplicate = Task("example/other", aliases=("example/task",))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate(Suite("example", (task, duplicate)))
        with self.assertRaisesRegex(ValueError, "suite-qualified"):
            validate(Suite("example", (Task("not-qualified"),)))
        with self.assertRaisesRegex(ValueError, "missing copied asset"):
            validate(
                Suite("example", (Task("example/task", copies=(copy("nope", "x"),)),))
            )

    def test_validate_rejects_missing_assets_in_every_declaration_kind(self) -> None:
        missing = Path("/definitely/missing")
        verifier = SharedVerifier("shared", missing)
        cases = (
            (
                "baked",
                Task(
                    "example/task",
                    environment=Environment(
                        agent=DockerBuild(
                            ImageRef("example/image", "v1"),
                            (bake(missing, "/opt/input", into="agent"),),
                        )
                    ),
                ),
            ),
            (
                "fixture",
                Task(
                    "example/task",
                    cases=(Case("case", fixtures=(fixture(missing, "input"),)),),
                ),
            ),
            (
                "solution",
                Task(
                    "example/task",
                    solution=Solution((copy(missing, "solve.sh"),)),
                ),
            ),
            ("verifier", Task("example/task", verifiers=(VerifierUse(verifier),))),
            (
                "verifier adapter",
                Task(
                    "example/task",
                    verifiers=(
                        VerifierUse(SharedVerifier("shared", Path(".")), missing),
                    ),
                ),
            ),
        )
        for label, task in cases:
            with (
                self.subTest(label=label),
                self.assertRaisesRegex(ValueError, f"missing {label} asset"),
            ):
                validate(Suite("example", (task,)))

    def test_validate_rejects_legacy_policy_duplicate_environment_and_adapter(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            (source / "task.toml").write_text("[task]\nname = 'example/task'\n")
            legacy = Task("example/task", source=source)
            with self.assertRaisesRegex(ValueError, "legacy sources are disabled"):
                validate(
                    Suite(
                        "example",
                        (legacy,),
                        policy=Policy(allow_legacy_sources=False),
                    )
                )

            duplicate_variables = Task(
                "example/task",
                environment=Environment(variables=(env("ONE"), env("ONE"))),
            )
            with self.assertRaisesRegex(ValueError, "variable declarations"):
                validate(Suite("example", (duplicate_variables,)))
            duplicate_services = Task(
                "example/task",
                environment=Environment(
                    services=(
                        runtime_service("api", ImageRef("example/api", "v1")),
                        runtime_service("api", ImageRef("example/api", "v2")),
                    )
                ),
            )
            with self.assertRaisesRegex(ValueError, "service names"):
                validate(Suite("example", (duplicate_services,)))

            verifier = root / "verifier"
            verifier.mkdir()
            contract = AdapterContract(PurePosixPath("adapter.py"), ("run",))
            use = VerifierUse(SharedVerifier("shared", verifier, contract))
            with self.assertRaisesRegex(ValueError, "missing verifier adapter"):
                validate(Suite("example", (Task("example/task", verifiers=(use,)),)))

    def test_lowering_supports_cases_solutions_and_verifier_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            payload = root / "payload.txt"
            payload.write_text("payload\n")
            fixture = root / "fixture.json"
            fixture.write_text("{}\n")
            verifier = root / "verifier"
            verifier.mkdir()
            (verifier / "check.py").write_text("def check():\n    pass\n")
            adapter = root / "adapter.py"
            adapter.write_text("value = 1\n")
            task = Task(
                "example/task",
                cases=(Case("one", {"CASE": "one"}, (Fixture(fixture, "one"),)),),
                solution=Solution((copy(payload, "run.sh"),)),
                verifiers=(VerifierUse(SharedVerifier("shared", verifier), adapter),),
                instruction=instruction_fragment("Do it."),
            )

            ir = lower_suite(
                Suite("example", (task,), policy=Policy(require_image_locks=False))
            ).tasks[0]
            assets = {asset.destination.as_posix() for asset in ir.assets}

            self.assertTrue(
                {
                    "tests/fixtures/one",
                    "solution/run.sh",
                    "tests/check.py",
                    "tests/adapter.py",
                    "instruction.md",
                    "task.toml",
                }.issubset(assets)
            )
            self.assertEqual(ir.environment, {"CASE": "one"})

    def test_lowering_merges_environment_into_legacy_task_toml_and_skips_manifest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source"
            source.mkdir()
            (source / "task.toml").write_text(
                "[task]\nname = 'example/task'\n[environment.env]\nEXISTING = 'yes'\n"
            )
            (source / MANIFEST).write_text("{}\n")
            task = Task(
                "example/task",
                source=source,
                environment=Environment(
                    agent=DockerBuild(ImageRef("example/image", "v1")),
                    variables=(env("ADDED", default="value"),),
                ),
            )

            ir = lower_suite(
                Suite("example", (task,), policy=Policy(require_image_locks=False))
            ).tasks[0]
            assets = {asset.destination.as_posix(): asset for asset in ir.assets}

            self.assertNotIn(MANIFEST, assets)
            self.assertIn(b"EXISTING = 'yes'", assets["task.toml"].source.read_bytes())
            self.assertIn(b'ADDED = "value"', assets["task.toml"].source.read_bytes())

    def test_lowering_copies_a_verifier_without_an_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            verifier = Path(temporary_directory) / "verifier"
            verifier.mkdir()
            (verifier / "check.py").write_text("def check():\n    pass\n")
            task = Task(
                "example/task",
                verifiers=(VerifierUse(SharedVerifier("shared", verifier)),),
            )
            ir = lower_suite(
                Suite("example", (task,), policy=Policy(require_image_locks=False))
            ).tasks[0]
            self.assertIn(
                PurePosixPath("tests/check.py"),
                {asset.destination for asset in ir.assets},
            )

    def test_lowering_keeps_unlocked_images_when_policy_allows_them(self) -> None:
        task = Task(
            "example/task",
            environment=Environment(
                services=(runtime_service("api", ImageRef("example/api", "v1")),)
            ),
        )
        ir = lower_suite(
            Suite("example", (task,), policy=Policy(require_image_locks=False))
        ).tasks[0]
        self.assertEqual(ir.resolved_images[0].digest, "")

    def test_emit_replaces_managed_output_and_rejects_unmanaged_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            task = Task("example/task")
            suite = lower_suite(
                Suite("example", (task,), policy=Policy(require_image_locks=False))
            )
            output = root / "output"
            rendered = emit(suite, output)[0]
            (rendered / "stale.txt").write_text("stale")
            emit(suite, output)
            self.assertFalse((rendered / "stale.txt").exists())

            unmanaged = output / "example" / "other"
            unmanaged.mkdir(parents=True)
            other = TaskIR("example/other", "other", (), (), {}, (), ())
            with self.assertRaisesRegex(ValueError, "unmanaged"):
                emit(SuiteIR("example", (other,), None), output)

    def test_emit_copies_dataset_and_preserves_declared_file_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            dataset = root / "dataset.toml"
            dataset.write_text("[dataset]\n")
            source = root / "source.sh"
            source.write_text("#!/bin/sh\n")
            asset = Asset(
                SourceRef(path=source),
                PurePosixPath("solution/run.sh"),
                "solution",
                Provenance("test"),
                0o755,
            )
            task = TaskIR("example/task", "task", (), (asset,), {}, (), ())
            emitted = emit(SuiteIR("example", (task,), dataset), root / "output")
            target = emitted[0] / "solution/run.sh"

            self.assertEqual(target.read_text(), "#!/bin/sh\n")
            self.assertTrue(target.stat().st_mode & stat.S_IXUSR)
            self.assertEqual(
                (root / "output/example/dataset.toml").read_text(), "[dataset]\n"
            )

    def test_manifest_and_task_differences_handle_metadata_and_nested_files(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            rendered = root / "rendered"
            for directory in (source, rendered):
                (directory / "environment").mkdir(parents=True)
                (directory / "task.toml").write_text("[task]\n")
                (directory / MANIFEST).write_text("{}\n")
            (source / "environment/Dockerfile").write_text("FROM one\n")
            (rendered / "environment/Dockerfile").write_text("FROM two\n")
            (rendered / "only-rendered.txt").write_text("extra\n")

            self.assertEqual(
                task_differences(source, rendered),
                ["environment/Dockerfile", "only-rendered.txt"],
            )
            task = TaskIR(
                "example/task",
                "task",
                ("example/old",),
                (
                    Asset(
                        SourceRef(content=b"generated"),
                        PurePosixPath("task.toml"),
                        "runtime",
                        Provenance("generated"),
                    ),
                ),
                {},
                (),
                (),
            )
            parsed = json.loads(manifest(task))
            self.assertIsNone(parsed["assets"]["task.toml"]["source"])
            self.assertEqual(parsed["aliases"], ["example/old"])

    def test_task_slug_and_destination_reject_malformed_or_escaping_values(
        self,
    ) -> None:
        with self.assertRaisesRegex(ValueError, "suite-qualified"):
            task_slug(Task("task"))
        task = TaskIR("example/task", "task", (), (), {}, (), ())
        with self.assertRaisesRegex(ValueError, "Suite names"):
            destination(Path("output"), SuiteIR("../../escape", (task,), None), task)
        escaping_task = TaskIR("example/escape", "../escape", (), (), {}, (), ())
        with self.assertRaisesRegex(ValueError, "escapes"):
            destination(
                Path("output"),
                SuiteIR("example", (escaping_task,), None),
                escaping_task,
            )

    def test_write_asset_uses_rendered_content_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            target = Path(temporary_directory) / "nested/output.txt"
            asset = Asset(
                SourceRef(content=b"rendered"),
                PurePosixPath("output.txt"),
                "runtime",
                Provenance("test"),
            )
            _write_asset(asset, target)
            self.assertEqual(target.read_bytes(), b"rendered")

    def test_load_suite_rejects_unknown_and_invalid_modules(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown suite"):
            load_suite("unknown")
        with (
            patch("evalkit.compiler.build.SUITE_MODULES", {"example": "example"}),
            patch(
                "evalkit.compiler.build.importlib.import_module",
                return_value=SimpleNamespace(SUITE=object()),
            ),
            self.assertRaisesRegex(TypeError, "must be an evalkit.api.Suite"),
        ):
            load_suite("example")

    def test_emit_rejects_harbor_hash_changes_for_legacy_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            source.mkdir()
            (source / "task.toml").write_text("[task]\nname = 'example/task'\n")
            suite = lower_suite(
                Suite("example", (Task("example/task", source=source),))
            )
            with (
                patch(
                    "evalkit.compiler.build.content_hash",
                    side_effect=("source", "output"),
                ),
                self.assertRaisesRegex(RuntimeError, "Harbor hash changed"),
            ):
                emit(suite, root / "output")

    def test_check_reports_missing_and_changed_generated_tasks(self) -> None:
        task = TaskIR("example/task", "task", (), (), {}, (), ())
        suite = SuiteIR("example", (task,), None)
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "output"
            with (
                patch("evalkit.compiler.build.load_suite"),
                patch("evalkit.compiler.build.lower_suite", return_value=suite),
                patch("evalkit.compiler.build.diff", return_value={}),
                self.assertRaisesRegex(ValueError, "Missing generated tasks"),
            ):
                check("example", output)

            (output / "example/task").mkdir(parents=True)
            with (
                patch("evalkit.compiler.build.load_suite"),
                patch("evalkit.compiler.build.lower_suite", return_value=suite),
                patch(
                    "evalkit.compiler.build.diff",
                    return_value={"example/task": ["task.toml"]},
                ),
                self.assertRaisesRegex(
                    ValueError,
                    "Generated task definitions differ: example/task: task.toml",
                ),
            ):
                check("example", output)
