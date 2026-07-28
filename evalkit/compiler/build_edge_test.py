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
    Bake,
    Case,
    DockerBuild,
    Environment,
    Fixture,
    ImageRef,
    InstructionDoc,
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
from evalkit.api import (
    Policy as ApiPolicy,
)
from evalkit.compiler.build import (
    MANIFEST,
    _rendered_differences,
    _write_asset,
    check,
    destination,
    diff,
    emit,
    load_suite,
    lower_suite,
    manifest,
    task_differences,
    task_slug,
    validate,
)
from evalkit.ir import Asset, Provenance, SourceRef, SuiteIR, TaskIR


def Policy(**kwargs: object) -> ApiPolicy:
    """Allow focused compiler tests to exercise incomplete declarations."""
    return ApiPolicy(allow_incomplete_tasks=True, **kwargs)


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
        with self.assertRaisesRegex(ValueError, "fully declared tasks require"):
            validate(Suite("example", (Task("example/task"),)))
        for task in (
            Task("example/task", instruction=InstructionDoc("# Task")),
            Task(
                "example/task",
                environment=Environment(
                    agent=DockerBuild(ImageRef("example/image", "v1"))
                ),
            ),
            Task(
                "example/task",
                environment=Environment(
                    verifier=DockerBuild(ImageRef("example/image", "v1"))
                ),
            ),
            Task(
                "example/task",
                verifiers=(VerifierUse(SharedVerifier("shared", Path("."))),),
            ),
            Task("example/task", solution=Solution()),
        ):
            with (
                self.subTest(task=task),
                self.assertRaisesRegex(ValueError, "fully declared tasks require"),
            ):
                validate(Suite("example", (task,)))
        with self.assertRaisesRegex(ValueError, "duplicate task output slugs"):
            validate(
                Suite(
                    "example",
                    (Task("first/shared"), Task("second/shared")),
                    policy=Policy(),
                )
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

    def test_validate_rejects_unsupported_environment_and_escaping_destinations(
        self,
    ) -> None:
        cases = (
            (
                "task asset destination",
                Task(
                    "example/task",
                    instruction=InstructionDoc("# Task", PurePosixPath("../outside")),
                ),
            ),
            (
                "different environments",
                Task(
                    "example/task",
                    cases=(Case("one", {"CASE": "one"}), Case("two", {"CASE": "two"})),
                ),
            ),
        )
        for message, task in cases:
            with (
                self.subTest(message=message),
                self.assertRaisesRegex(ValueError, message),
            ):
                validate(Suite("example", (task,), policy=Policy()))

    def test_rendering_rejects_bakes_assigned_to_the_wrong_build_role(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "payload"
            source.write_text("payload")
            task = Task(
                "example/task",
                environment=Environment(
                    agent=DockerBuild(
                        ImageRef("example/image", "v1"),
                        (bake(source, "/opt/payload", into="verifier"),),
                    )
                ),
            )
            with self.assertRaisesRegex(ValueError, "cannot be used by agent"):
                lower_suite(
                    Suite(
                        "example",
                        (task,),
                        policy=Policy(require_image_locks=False),
                    )
                )

            invalid_role = Task(
                "example/task",
                environment=Environment(
                    agent=DockerBuild(
                        ImageRef("example/image", "v1"),
                        (Bake(source, PurePosixPath("/opt/payload"), "runtime"),),  # type: ignore[arg-type]
                    )
                ),
            )
            with self.assertRaisesRegex(ValueError, "invalid bake role"):
                validate(Suite("example", (invalid_role,), policy=Policy()))

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
                validate(Suite("example", (duplicate_variables,), policy=Policy()))
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
                validate(Suite("example", (duplicate_services,), policy=Policy()))

            verifier = root / "verifier"
            verifier.mkdir()
            contract = AdapterContract(PurePosixPath("adapter.py"), ("run",))
            use = VerifierUse(SharedVerifier("shared", verifier, contract))
            with self.assertRaisesRegex(ValueError, "missing verifier adapter"):
                validate(
                    Suite(
                        "example",
                        (Task("example/task", verifiers=(use,)),),
                        policy=Policy(),
                    )
                )

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
            dataset_output = (root / "output/example/dataset.toml").read_text()
            self.assertIn('name = "example/task"', dataset_output)
            self.assertIn('digest = "sha256:', dataset_output)

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
                        Provenance("generated", "replace generated task TOML"),
                    ),
                ),
                {},
                (),
                (),
            )
            parsed = json.loads(manifest(task))
            self.assertIsNone(parsed["assets"]["task.toml"]["source"])
            self.assertEqual(
                parsed["assets"]["task.toml"]["override_reason"],
                "replace generated task TOML",
            )
            self.assertEqual(parsed["aliases"], ["example/old"])

            output = root / "declared"
            output.mkdir()
            (output / "task.toml").write_bytes(b"stale")
            self.assertEqual(_rendered_differences(task, output), ["task.toml"])

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

    def test_solution_entrypoint_and_contract_adapter_paths_are_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            solution = root / "run.sh"
            solution.write_text("#!/bin/sh\n")
            verifier = root / "verifier"
            verifier.mkdir()
            adapter = root / "local_adapter.py"
            adapter.write_text("def check():\n    pass\n")
            task = Task(
                "example/task",
                solution=Solution((copy(solution, "run.sh"),), PurePosixPath("run.sh")),
                verifiers=(
                    VerifierUse(
                        SharedVerifier(
                            "shared",
                            verifier,
                            AdapterContract(
                                PurePosixPath("adapters/task.py"), ("check",)
                            ),
                        ),
                        adapter,
                    ),
                ),
            )
            ir = lower_suite(
                Suite("example", (task,), policy=Policy(require_image_locks=False))
            ).tasks[0]
            assets = {
                asset.destination.as_posix(): asset.source.read_bytes()
                for asset in ir.assets
            }
            self.assertEqual(assets["solution/solve.sh"], b"#!/bin/sh\n")
            self.assertEqual(assets["tests/adapters/task.py"], adapter.read_bytes())

            direct_entrypoint = Task(
                "example/direct",
                solution=Solution(
                    (copy(solution, "solve.sh"),), PurePosixPath("solve.sh")
                ),
            )
            direct_ir = lower_suite(
                Suite(
                    "example",
                    (direct_entrypoint,),
                    policy=Policy(require_image_locks=False),
                )
            ).tasks[0]
            self.assertEqual(
                [asset.destination.as_posix() for asset in direct_ir.assets].count(
                    "solution/solve.sh"
                ),
                1,
            )

    def test_solution_entrypoint_must_reference_an_asset(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "run.sh"
            source.write_text("#!/bin/sh\n")
            task = Task(
                "example/task",
                solution=Solution(
                    (copy(source, "run.sh"),), PurePosixPath("missing.sh")
                ),
            )
            with self.assertRaisesRegex(ValueError, "must name a solution asset"):
                lower_suite(
                    Suite(
                        "example",
                        (task,),
                        policy=Policy(require_image_locks=False),
                    )
                )

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

    def test_diff_reports_stale_fully_declared_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "output"
            original = Suite(
                "example",
                (Task("example/task", instruction=InstructionDoc("original")),),
                policy=Policy(require_image_locks=False),
            )
            changed = Suite(
                "example",
                (Task("example/task", instruction=InstructionDoc("changed")),),
                policy=Policy(require_image_locks=False),
            )
            emit(lower_suite(original), output)
            with patch("evalkit.compiler.build.load_suite", return_value=changed):
                differences = diff("example", output)
            self.assertEqual(differences, {"example/task": ["instruction.md"]})
