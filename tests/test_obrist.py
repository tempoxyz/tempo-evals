import ast
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from click.testing import CliRunner
from pydantic import ValidationError

from obrist import BenchmarkJobSpec, PackagedSuiteSpec, ProfileSpec, benchmark_job_collection
from obrist.backends.harbor.emit import TemplateName, _override_template, compile_collection
from obrist.cli import main
from obrist.compiler.headers import AUTO_GENERATED_TEXT, add_generated_header, supports_generated_header
from obrist.compiler.paths import assert_allowed_output_path
from obrist.dsl import AgentSpec, Sandbox
from obrist.registry import load_collection

REPO_ROOT = Path(__file__).resolve().parents[1]


class ObristTests(unittest.TestCase):
    def test_generated_header_formats(self) -> None:
        self.assertTrue(add_generated_header(Path("task.toml"), "[task]\n").startswith("# AUTO-GENERATED"))
        self.assertTrue(add_generated_header(Path("instruction.md"), "body\n").startswith("<!-- AUTO-GENERATED"))
        self.assertTrue(add_generated_header(Path("check.py"), "print('x')\n").startswith("# AUTO-GENERATED"))
        self.assertTrue(add_generated_header(Path("server.mjs"), "import 'x';\n").startswith("// AUTO-GENERATED"))
        shell = add_generated_header(Path("solve.sh"), "#!/usr/bin/env bash\necho ok\n")
        self.assertTrue(shell.startswith("#!/usr/bin/env bash\n# AUTO-GENERATED"))
        self.assertEqual(add_generated_header(Path("manifest.json"), "{}\n"), "{}\n")

    def test_guarded_output_paths(self) -> None:
        for protected in ("obrist/out", "datasets/out", "tasks/out", "shared/out"):
            with self.subTest(protected=protected):
                with self.assertRaises(ValueError):
                    assert_allowed_output_path(REPO_ROOT / protected, REPO_ROOT)

    def test_tempobench_compiles_without_mutating_sources(self) -> None:
        before = _git_status("datasets/tempobench")
        collection = load_collection("tempobench")
        with tempfile.TemporaryDirectory() as tmp:
            compiled = compile_collection(collection, None, Path(tmp), sync=False)
            self.assertTrue(compiled.manifest_path.exists())
            self.assertEqual(compiled.run_name, "tempobench")
            self.assertIn('"generated_by": "obrist"', compiled.manifest_path.read_text())
            task_toml = compiled.root / "tasks/transfer-with-memo-docs/task.toml"
            instruction = compiled.root / "tasks/transfer-with-memo-docs/instruction.md"
            criteria = compiled.root / "tasks/transfer-with-memo-docs/tests/correctness/criteria.py"
            self.assertIn(AUTO_GENERATED_TEXT, task_toml.read_text())
            self.assertIn(AUTO_GENERATED_TEXT, instruction.read_text())
            criteria_text = criteria.read_text()
            self.assertIn(AUTO_GENERATED_TEXT, criteria_text)
            self.assertIn("import tempo_bench_rewardkit", criteria_text)
            self.assertIn("rk.tempo_source_patterns", criteria_text)
            test_package = compiled.root / "tasks/transfer-with-memo-docs/tests/package.json"
            test_package_payload = json.loads(test_package.read_text())
            self.assertEqual(
                "file:./tempo-bench-verifier",
                test_package_payload["dependencies"]["@tempo-bench/verifier"],
            )
            self.assertTrue((compiled.root / "shared").exists())
            self.assertTrue((compiled.root / "tasks/transfer-with-memo-docs/environment/docker-compose.yaml").exists())
            self.assertTrue((compiled.root / "tasks/transfer-with-memo-docs/tests/tempo-bench-verifier").exists())
            self.assertTrue((compiled.root / "tasks/transfer-with-memo-docs/tests/reward.toml").exists())
            solution_source = compiled.root / "tasks/transfer-with-memo-docs/solution/src/index.ts"
            self.assertIn("function required", solution_source.read_text(encoding="utf-8"))
            self.assertEqual(
                [], [str(path.relative_to(compiled.root)) for path in compiled.root.rglob("*") if path.is_symlink()]
            )
            missing_headers: list[str] = []
            for path in compiled.root.rglob("*"):
                if path.is_file() and not path.is_symlink() and supports_generated_header(path):
                    first_lines = path.read_text(encoding="utf-8").splitlines()[:3]
                    if not any(AUTO_GENERATED_TEXT in line for line in first_lines):
                        missing_headers.append(str(path.relative_to(compiled.root)))
            self.assertEqual([], missing_headers)
        after = _git_status("datasets/tempobench")
        self.assertEqual(before, after)

    def test_tempobench_source_tasks_do_not_contain_materialized_shared_assets(self) -> None:
        task_root = REPO_ROOT / "datasets/tempobench/tasks"
        self.assertFalse(task_root.exists())
        self.assertFalse((REPO_ROOT / "datasets/tempobench/tempobench").exists())

    def test_dsl_validates_and_freezes_inputs(self) -> None:
        with self.assertRaises(ValidationError):
            Sandbox(egress=cast(Any, "invalid"))
        agent = AgentSpec(name="oracle", env={"TOKEN": "redacted"})
        with self.assertRaises(TypeError):
            cast(Any, agent.env)["TOKEN"] = "changed"

    def test_tempobench_discovers_dataset_tasks(self) -> None:
        collection = load_collection("tempobench")
        task_names = tuple(task.name for job in collection.suite("default").jobs for task in job.tasks)
        self.assertEqual(("default",), tuple(suite.name for suite in collection.suites))
        self.assertEqual(12, len(task_names))
        self.assertIn("tempo/transfer-with-memo-docs", task_names)
        self.assertIn("tempo/stablecoin-dex-swap-mcp", task_names)
        self.assertEqual(
            tuple(name.rsplit("/", 1)[-1] for name in task_names),
            collection.suite("default").jobs[0].task_name_globs,
        )

    def test_profile_spec_derives_common_fields_from_name(self) -> None:
        profile = ProfileSpec(name="mcp", instruction="Use the MCP profile.")
        self.assertEqual("mcp", profile.suffix)
        self.assertEqual("mcp", profile.keyword)
        self.assertEqual("(mcp profile).", profile.description_suffix)

        overridden = ProfileSpec(
            name="docs",
            suffix="documentation",
            keyword="manual",
            description_suffix="(custom docs profile).",
            instruction="Use docs.",
        )
        self.assertEqual("documentation", overridden.suffix)
        self.assertEqual("manual", overridden.keyword)
        self.assertEqual("(custom docs profile).", overridden.description_suffix)

    def test_benchmark_job_collection_builder_standardizes_layout(self) -> None:
        from datasets.tempobench.spec import TEMPO_BENCH

        self.assertIsInstance(TEMPO_BENCH, BenchmarkJobSpec)
        collection = benchmark_job_collection(
            TEMPO_BENCH.model_copy(
                update={
                    "collection_name": "examplebench",
                    "suites": (PackagedSuiteSpec(name="default", job_name="example-local"),),
                }
            )
        )
        self.assertEqual(TEMPO_BENCH.shared_dir, collection.shared_dir)
        self.assertEqual("example-local", collection.suite("default").job_name)
        self.assertEqual("tempo-bench", collection.suite("default").jobs[0].name)

    def test_tempobench_private_key_envs_are_allowlisted_fixtures(self) -> None:
        from datasets.tempobench.spec import LOCALNET_PRIVATE_KEYS, TEMPO_BENCH

        envs = [TEMPO_BENCH.environment.env]
        envs.extend(profile.env for profile in TEMPO_BENCH.profiles)
        envs.extend(case.env for case in TEMPO_BENCH.cases)

        for env in envs:
            with self.assertRaises(TypeError):
                cast(Any, env)["UNSAFE_MUTATION"] = "blocked"
            for name, value in env.items():
                if name.endswith("_PRIVATE_KEY"):
                    self.assertIn(value, LOCALNET_PRIVATE_KEYS, name)

    def test_only_harbor_backend_imports_harbor_package(self) -> None:
        violations: list[str] = []
        for path in (REPO_ROOT / "obrist").rglob("*.py"):
            relative = path.relative_to(REPO_ROOT)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                module: str | None = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "harbor" or alias.name.startswith("harbor."):
                            module = alias.name
                elif isinstance(node, ast.ImportFrom):
                    if node.module == "harbor" or (node.module or "").startswith("harbor."):
                        module = node.module
                if module and "obrist/backends/harbor" not in str(relative):
                    violations.append(f"{relative}: {module}")
        for path in (REPO_ROOT / "datasets").rglob("*.py"):
            relative = path.relative_to(REPO_ROOT)
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                harbor_module: str | None = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "harbor" or alias.name.startswith("harbor."):
                            harbor_module = alias.name
                elif isinstance(node, ast.ImportFrom):
                    if node.module == "harbor" or (node.module or "").startswith("harbor."):
                        harbor_module = node.module
                if harbor_module:
                    violations.append(f"{relative}: {harbor_module}")
        self.assertEqual([], violations)

    def test_tempobench_does_not_import_obrist_harbor_backend(self) -> None:
        violations: list[str] = []
        for path in (REPO_ROOT / "datasets/tempobench").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("obrist.backends.harbor"):
                    violations.append(str(path.relative_to(REPO_ROOT)))
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("obrist.backends.harbor"):
                            violations.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual([], violations)

    def test_cli_does_not_eagerly_import_harbor_backend(self) -> None:
        path = REPO_ROOT / "obrist/cli.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        top_level_imports = [node for node in tree.body if isinstance(node, ast.Import | ast.ImportFrom)]
        modules = [alias.name for node in top_level_imports if isinstance(node, ast.Import) for alias in node.names] + [
            node.module or "" for node in top_level_imports if isinstance(node, ast.ImportFrom)
        ]
        self.assertFalse(any(module.startswith("obrist.backends.harbor") for module in modules))

    def test_cli_exposes_compile_only(self) -> None:
        result = CliRunner().invoke(main, ["--help"])
        self.assertEqual(0, result.exit_code)
        self.assertIn("compile", result.output)
        self.assertNotIn(" run", result.output)
        self.assertNotIn(" view", result.output)
        self.assertNotIn(" diff", result.output)

    def test_cli_compile_writes_generated_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = CliRunner().invoke(main, ["compile", "tempobench", "--out", tmp, "--no-sync"])
            self.assertEqual(0, result.exit_code)
            payload = json.loads(result.output)
            manifest_path = Path(payload["manifest"])
            self.assertEqual((Path(tmp) / "tempobench" / "manifest.json").resolve(), manifest_path)
            self.assertTrue(manifest_path.exists())

    def test_obrist_has_no_run_or_result_layer(self) -> None:
        self.assertFalse((REPO_ROOT / "obrist/backends/harbor/run.py").exists())
        self.assertFalse((REPO_ROOT / "obrist/results").exists())

    def test_harbor_backend_templates_and_emitter_are_not_tempo_specific(self) -> None:
        violations: list[str] = []
        for path in (REPO_ROOT / "obrist/backends/harbor/templates").glob("*.j2"):
            content = path.read_text(encoding="utf-8")
            if "tempo" in content.lower():
                violations.append(str(path.relative_to(REPO_ROOT)))
        emit_path = REPO_ROOT / "obrist/backends/harbor/emit.py"
        if "tempo" in emit_path.read_text(encoding="utf-8").lower():
            violations.append(str(emit_path.relative_to(REPO_ROOT)))
        self.assertEqual([], violations)

    def test_all_harbor_templates_support_dataset_inheritance(self) -> None:
        for template_name in TemplateName:
            with self.subTest(template=template_name.value):
                with tempfile.TemporaryDirectory() as tmp:
                    override_path = Path(tmp) / template_name.value
                    override_path.write_text(
                        f'{{% extends "obrist/{template_name.value}" %}}\n'
                        "{% block content %}override {{ marker }}{% endblock %}\n",
                        encoding="utf-8",
                    )
                    rendered = _override_template(override_path, template_name).render({"marker": "ok"})
                    self.assertEqual("override ok", rendered.strip())

    def test_tempobench_overrides_parent_criteria_template(self) -> None:
        template_path = REPO_ROOT / "datasets/tempobench/templates/criteria.py.j2"
        content = template_path.read_text(encoding="utf-8")
        self.assertIn('{% extends "obrist/criteria.py.j2" %}', content)
        self.assertIn("{% block imports %}", content)
        self.assertIn("{% block criteria %}", content)

    def test_package_init_files_have_module_docstrings(self) -> None:
        missing_docstrings: list[str] = []
        for root in (REPO_ROOT / "obrist", REPO_ROOT / "datasets"):
            for path in root.rglob("__init__.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                if not ast.get_docstring(tree):
                    missing_docstrings.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual([], missing_docstrings)


def _git_status(*paths: str) -> str:
    return subprocess.check_output(
        ["git", "status", "--short", "--", *paths],
        cwd=REPO_ROOT,
        text=True,
    )


if __name__ == "__main__":
    unittest.main()
