import json
import os
import shutil
import subprocess
from enum import StrEnum
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Final

from jinja2 import DictLoader, Environment, FileSystemLoader, PrefixLoader, StrictUndefined, Template

from obrist.collections import BenchmarkJobSpec, ProfileSpec, TaskCaseSpec
from obrist.compiler.headers import add_generated_header, supports_generated_header
from obrist.compiler.models import CompileResult
from obrist.compiler.paths import assert_allowed_output_path
from obrist.dsl import BenchmarkCollection, Job, Suite, Task


class HarborPath(StrEnum):
    """Generated Harbor workspace filenames and directory names."""

    SHARED = "shared"
    TASKS = "tasks"
    DATASET_TOML = "dataset.toml"
    JOB_YAML = "job.yaml"
    MANIFEST_JSON = "manifest.json"


class ManifestKey(StrEnum):
    """Manifest keys written by the Harbor emitter."""

    GENERATED_BY = "generated_by"
    COLLECTION = "collection"
    SUITE = "suite"
    BACKEND = "backend"
    TASKS = "tasks"
    ROOT = "root"


class GeneratedTextSuffix(StrEnum):
    """File suffixes treated as generated text when copied or emitted."""

    CFG = ".cfg"
    CSS = ".css"
    HTML = ".html"
    JS = ".js"
    JSON = ".json"
    JSONC = ".jsonc"
    MD = ".md"
    MJS = ".mjs"
    PY = ".py"
    SH = ".sh"
    TOML = ".toml"
    TS = ".ts"
    TXT = ".txt"
    YAML = ".yaml"
    YML = ".yml"


class GeneratedTextName(StrEnum):
    """Filename-only generated text matches."""

    DOCKERFILE = "Dockerfile"
    MAKEFILE = "Makefile"


class HarborCommand(StrEnum):
    """Harbor CLI command fragments used during compilation."""

    HARBOR = "harbor"
    SYNC = "sync"


class TemplateName(StrEnum):
    """Packaged Jinja templates used to render Harbor files."""

    DATASET = "dataset.toml.j2"
    JOB = "job.yaml.j2"
    TASK = "task.toml.j2"
    INSTRUCTION = "instruction.md.j2"
    CRITERIA = "criteria.py.j2"
    REWARD = "reward.toml.j2"
    TEST_PACKAGE = "test-package.json.j2"


BACKEND_NAME: Final = "harbor"
GENERATED_BY: Final = "obrist"
DEFAULT_DATASET_AUTHOR_NAME: Final = "Obrist"
EMPTY_DIGEST: Final = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
JOBS_DIR: Final = "jobs"
ORACLE_AGENT_NAME: Final = "oracle"
IGNORED_COPY_PATTERNS: Final = ("node_modules", "package-lock.json", "__pycache__")
TEXT_SUFFIXES: Final[frozenset[str]] = frozenset(suffix.value for suffix in GeneratedTextSuffix)
TEXT_NAMES: Final[frozenset[str]] = frozenset(name.value for name in GeneratedTextName)
JINJA_ENV: Final = Environment(undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)


def compile_collection(
    collection: BenchmarkCollection,
    suite_name: str | None,
    out: Path,
    *,
    sync: bool = True,
) -> CompileResult:
    """Compile a benchmark collection into a generated Harbor workspace."""

    suite = collection.suite(suite_name)
    repo_root = collection.repo_root.resolve()
    assert_allowed_output_path(out, repo_root)

    run_name = _run_name(collection, suite)
    root = (out / run_name).resolve()
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    source_tasks = collection.tasks_dir.resolve()
    source_shared = collection.shared_dir.resolve()
    selected_task_slugs = _task_slugs(suite)
    job_spec = _job_spec(collection)

    _copy_tree(source_shared, root / HarborPath.SHARED)
    tasks_root = root / HarborPath.TASKS
    tasks_root.mkdir()
    for slug in selected_task_slugs:
        task_root = tasks_root / slug
        if job_spec is None:
            _copy_tree(source_tasks / slug, task_root)
        else:
            generated_task = _generated_task(job_spec, slug)
            _write_generated_task(job_spec, generated_task[0], generated_task[1], task_root)
        _materialize_shared_task_assets(source_shared, task_root, job_spec)

    task_names = _task_names(suite)
    _write_text(tasks_root / HarborPath.DATASET_TOML, _dataset_toml(collection, suite, task_names, job_spec))
    _write_text(root / HarborPath.JOB_YAML, _job_yaml(collection, suite, job_spec))
    manifest_path = root / HarborPath.MANIFEST_JSON
    _write_json(
        manifest_path,
        {
            ManifestKey.GENERATED_BY: GENERATED_BY,
            ManifestKey.COLLECTION: collection.name,
            ManifestKey.SUITE: suite.name,
            ManifestKey.BACKEND: BACKEND_NAME,
            ManifestKey.TASKS: task_names,
            ManifestKey.ROOT: str(root),
        },
    )

    if sync:
        subprocess.run([HarborCommand.HARBOR, HarborCommand.SYNC, HarborPath.TASKS], cwd=root, check=True)
        _ensure_header(tasks_root / HarborPath.DATASET_TOML)

    return CompileResult(
        run_name=run_name,
        root=root,
        manifest_path=manifest_path,
        job_config=root / HarborPath.JOB_YAML,
        dataset=tasks_root / HarborPath.DATASET_TOML,
    )


def _suite_tasks(suite: Suite) -> tuple[Task, ...]:
    tasks = tuple(task for job in suite.jobs for task in job.tasks)
    if not tasks:
        raise ValueError(f"Suite {suite.name!r} does not contain any tasks")
    return tasks


def _run_name(collection: BenchmarkCollection, suite: Suite) -> str:
    if suite.name == collection.default_suite:
        return collection.name
    return f"{collection.name}-{suite.name}"


def _task_slugs(suite: Suite) -> list[str]:
    slugs: list[str] = []
    for task in _suite_tasks(suite):
        slug = task.source_slug or task.name.rsplit("/", 1)[-1]
        if slug not in slugs:
            slugs.append(slug)
    return slugs


def _task_names(suite: Suite) -> list[str]:
    names: list[str] = []
    for job in suite.jobs:
        for task in job.tasks:
            name = task.name if "/" in task.name else f"{job.task_name_prefix}{task.name}"
            if name not in names:
                names.append(name)
    return names


def _primary_job(suite: Suite) -> Job:
    try:
        return suite.jobs[0]
    except IndexError as error:
        raise ValueError(f"Suite {suite.name!r} does not contain any jobs") from error


def _job_spec(collection: BenchmarkCollection) -> BenchmarkJobSpec | None:
    spec = collection.metadata.get("job_spec")
    return spec if isinstance(spec, BenchmarkJobSpec) else None


def _generated_task(spec: BenchmarkJobSpec, slug: str) -> tuple[TaskCaseSpec, ProfileSpec]:
    for case in spec.cases:
        for profile in spec.profiles:
            if f"{case.slug}-{profile.suffix}" == slug:
                return case, profile
    raise KeyError(f"Unknown generated task slug {slug!r}")


def _write_generated_task(spec: BenchmarkJobSpec, case: TaskCaseSpec, profile: ProfileSpec, task_root: Path) -> None:
    task_root.mkdir(parents=True)
    env = dict(spec.environment.env)
    env.update(case.env)
    env.update(profile.env)
    keywords = tuple(dict.fromkeys((*case.keywords, profile.keyword)))
    _write_text(
        task_root / "task.toml",
        _render_template(
            spec,
            TemplateName.TASK,
            name=f"{spec.dataset_name.rsplit('/', 1)[0]}/{case.slug}-{profile.suffix}",
            description=f"{case.description} {profile.description_suffix}".strip(),
            keywords=keywords,
            category=spec.category,
            feature=case.slug,
            profile=profile.name,
            artifacts=spec.output.artifacts,
            verifier=spec.verifier,
            agent=spec.agent,
            environment=spec.environment,
            env=env,
            mcp_servers=profile.mcp_servers,
        ),
    )
    _write_text(
        task_root / "instruction.md",
        _render_template(
            spec,
            TemplateName.INSTRUCTION,
            title=case.title,
            prompt=case.prompt,
            profile_instruction=profile.instruction,
            execution_constraints=spec.execution_constraints,
            requirements=case.requirements,
        ),
    )
    _write_text(
        task_root / "tests/correctness/criteria.py",
        _criteria_py(spec, case, profile),
    )
    _write_text(task_root / "solution/package.json", spec.output.package_json)
    solve_path = task_root / "solution/solve.sh"
    _write_text(solve_path, spec.output.solve_sh)
    solve_path.chmod(solve_path.stat().st_mode | 0o111)
    _write_text(task_root / "solution/tsconfig.json", spec.output.tsconfig_json)
    _copy_solution(case.solution.path, task_root / "solution")


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    shutil.copytree(
        source,
        destination,
        symlinks=False,
        ignore=shutil.ignore_patterns(*IGNORED_COPY_PATTERNS),
    )
    for path in destination.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        if _is_text_path(path):
            _ensure_header(path)


def _copy_shared_path(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    if destination.exists() or destination.is_symlink():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        _copy_tree(source, destination)
    else:
        shutil.copy2(source, destination)
        if _is_text_path(destination):
            _ensure_header(destination)


def _copy_solution(source: Path, destination: Path) -> None:
    source = source.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Solution directory does not exist: {source}")
    for path in source.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        relative_path = path.relative_to(source)
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        if _is_text_path(target):
            _ensure_header(target)


def _materialize_shared_task_assets(shared_root: Path, task_root: Path, job_spec: BenchmarkJobSpec | None) -> None:
    if job_spec is None:
        return

    for asset in job_spec.shared_assets:
        _copy_shared_path(shared_root / asset.source, task_root / asset.destination)
    _write_text(task_root / "tests/package.json", _test_package_json(job_spec))
    if job_spec.quality_reward_source:
        _write_text(
            task_root / "tests/reward.toml",
            _render_template(
                job_spec,
                TemplateName.REWARD,
                quality_reward=(shared_root / job_spec.quality_reward_source).read_text(encoding="utf-8"),
            ),
        )


def _criteria_py(spec: BenchmarkJobSpec, case: TaskCaseSpec, profile: ProfileSpec) -> str:
    context = {
        "patterns": [{"name": pattern.name, "pattern": repr(pattern.pattern)} for pattern in case.source_patterns],
        "trajectory_pattern": repr(profile.trajectory_pattern) if profile.trajectory_pattern else None,
    }
    return _render_template(spec, TemplateName.CRITERIA, **context)


def _test_package_json(spec: BenchmarkJobSpec) -> str:
    return _render_template(spec, TemplateName.TEST_PACKAGE, dependencies=dict(spec.test_package.dependencies))


def _is_text_path(path: Path) -> bool:
    if path.name in TEXT_NAMES or path.suffix in TEXT_SUFFIXES:
        return True
    try:
        with path.open("rb") as file:
            return b"\0" not in file.read(2048)
    except OSError:
        return False


def _ensure_header(path: Path) -> None:
    if not supports_generated_header(path):
        return
    content = path.read_text(encoding="utf-8")
    next_content = add_generated_header(path, content)
    if next_content != content:
        path.write_text(next_content, encoding="utf-8")
        if os.access(path, os.X_OK):
            path.chmod(path.stat().st_mode | 0o111)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(add_generated_header(path, content), encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@lru_cache(maxsize=len(TemplateName))
def _template(name: TemplateName) -> Template:
    source = files("obrist.backends.harbor.templates").joinpath(name.value).read_text(encoding="utf-8")
    return JINJA_ENV.from_string(source)


def _render_template(spec: BenchmarkJobSpec | None, template_name: TemplateName, **context: object) -> str:
    override_path = _template_override_path(spec, template_name)
    if override_path is None:
        return _template(template_name).render(context)
    return _override_template(override_path, template_name).render(context)


def _template_override_path(spec: BenchmarkJobSpec | None, name: TemplateName) -> Path | None:
    if spec is None:
        return None
    overrides = {
        TemplateName.DATASET: spec.templates.dataset,
        TemplateName.JOB: spec.templates.job,
        TemplateName.TASK: spec.templates.task,
        TemplateName.INSTRUCTION: spec.templates.instruction,
        TemplateName.CRITERIA: spec.templates.criteria,
        TemplateName.REWARD: spec.templates.reward,
        TemplateName.TEST_PACKAGE: spec.templates.test_package,
    }
    return overrides[name]


def _override_template(path: Path, parent: TemplateName) -> Template:
    if not path.exists():
        raise FileNotFoundError(path)
    parent_source = files("obrist.backends.harbor.templates").joinpath(parent.value).read_text(encoding="utf-8")
    environment = Environment(
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        loader=PrefixLoader(
            {
                "dataset": FileSystemLoader(str(path.parent)),
                "obrist": DictLoader({parent.value: parent_source}),
            }
        ),
    )
    return environment.get_template(f"dataset/{path.name}")


def _dataset_toml(
    collection: BenchmarkCollection,
    suite: Suite,
    task_names: list[str],
    job_spec: BenchmarkJobSpec | None,
) -> str:
    job = _primary_job(suite)
    return _render_template(
        job_spec,
        TemplateName.DATASET,
        dataset_name=job.dataset_name or collection.name,
        dataset_description=job.dataset_description or f"{collection.name} benchmark compiled by Obrist",
        dataset_keywords=job.dataset_keywords,
        dataset_author_name=job.dataset_author_name or DEFAULT_DATASET_AUTHOR_NAME,
        tasks=[{"name": name, "digest": EMPTY_DIGEST} for name in task_names],
    )


def _job_yaml(collection: BenchmarkCollection, suite: Suite, job_spec: BenchmarkJobSpec | None) -> str:
    task_name_globs = tuple(dict.fromkeys(glob for job in suite.jobs for glob in job.task_name_globs))
    return _render_template(
        job_spec,
        TemplateName.JOB,
        job_name=suite.job_name or f"{collection.name}-{suite.name}-local",
        jobs_dir=JOBS_DIR,
        attempts=suite.attempts,
        oracle_agent_name=ORACLE_AGENT_NAME,
        tasks_path=HarborPath.TASKS,
        task_name_globs=task_name_globs,
    )
