from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeVar, cast

from pydantic import Field, field_validator, model_validator

from obrist.dsl import AgentSpec, BenchmarkCollection, Job, MCPServer, ObristModel, Suite, Task

MappingValue = TypeVar("MappingValue")


def _freeze_mapping(value: Mapping[str, MappingValue] | None) -> Mapping[str, MappingValue]:
    return MappingProxyType(dict(value or {}))


class PackagedSuiteSpec(ObristModel):
    """Suite settings for collection builders."""

    name: str
    job_name: str | None = None
    job_display_name: str | None = None
    attempts: int = 1
    agents: tuple[AgentSpec | str, ...] = ("oracle",)


class SourcePatternSpec(ObristModel):
    """Source-code pattern requirement emitted into Harbor criteria."""

    name: str
    pattern: str


class SolutionSpec(ObristModel):
    """Oracle solution directory copied into a generated task."""

    path: Path


class TaskCaseSpec(ObristModel):
    """One benchmark case before profile expansion."""

    slug: str
    title: str
    description: str
    keywords: tuple[str, ...]
    prompt: str
    requirements: tuple[str, ...]
    verifier_case: str
    env: Mapping[str, str] = Field(default_factory=dict, validate_default=True)
    source_patterns: tuple[SourcePatternSpec, ...]
    solution: SolutionSpec

    @field_validator("env")
    @classmethod
    def _freeze_env(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        return _freeze_mapping(value)


class ProfileSpec(ObristModel):
    """Profile overlay that expands each case into a concrete task."""

    name: str
    suffix: str = ""
    keyword: str = ""
    description_suffix: str = ""
    instruction: str
    env: Mapping[str, str] = Field(default_factory=dict, validate_default=True)
    mcp_servers: tuple[MCPServer, ...] = ()
    trajectory_pattern: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _default_named_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        name = data.get("name")
        if not isinstance(name, str):
            return data
        if not data.get("suffix"):
            data["suffix"] = name
        if not data.get("keyword"):
            data["keyword"] = name
        if not data.get("description_suffix"):
            data["description_suffix"] = f"({name} profile)."
        return data

    @field_validator("env")
    @classmethod
    def _freeze_env(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        return _freeze_mapping(value)


class EnvironmentDefaults(ObristModel):
    """Backend task environment defaults shared by generated cases."""

    build_timeout_sec: float = 600.0
    cpus: int = 2
    memory_mb: int = 4096
    storage_mb: int = 10240
    env: Mapping[str, str] = Field(default_factory=dict, validate_default=True)

    @field_validator("env")
    @classmethod
    def _freeze_env(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        return _freeze_mapping(value)


class VerifierDefaults(ObristModel):
    """Backend verifier defaults shared by generated cases."""

    timeout_sec: float = 300.0
    environment_mode: str = "shared"


class AgentDefaults(ObristModel):
    """Backend agent defaults shared by generated cases."""

    timeout_sec: float = 900.0


class TypeScriptAppDefaults(ObristModel):
    """Standard TypeScript app output contract and oracle files."""

    artifacts: tuple[str, ...] = ("/app/package.json", "/app/src")
    package_json: str = """{
  "private": true,
  "type": "module",
  "scripts": {
    "build": "tsc -p tsconfig.json --noEmit",
    "run": "tsx src/index.ts"
  },
  "dependencies": {
    "@types/node": "^22.15.30",
    "tsx": "^4.20.3",
    "typescript": "^5.8.3",
    "viem": "^2.53.1"
  }
}
"""
    tsconfig_json: str = """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "types": ["node"],
    "skipLibCheck": true
  },
  "include": ["src/**/*.ts"]
}
"""
    solve_sh: str = """#!/usr/bin/env bash
set -euo pipefail

solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
app_dir="${APP_DIR:-/app}"
mkdir -p "$app_dir"
cp -R "$solution_dir/." "$app_dir/"
rm -f "$app_dir/solve.sh"
"""


class HarborTemplateOverrides(ObristModel):
    """Dataset template files that extend packaged Obrist Harbor templates."""

    dataset: Path | None = None
    job: Path | None = None
    task: Path | None = None
    instruction: Path | None = None
    criteria: Path | None = None
    reward: Path | None = None
    test_package: Path | None = None


class NodeTestPackageSpec(ObristModel):
    """Node package dependencies emitted into generated Harbor test directories."""

    dependencies: Mapping[str, str] = Field(default_factory=dict, validate_default=True)

    @field_validator("dependencies")
    @classmethod
    def _freeze_dependencies(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        return _freeze_mapping(value)


class SharedAssetSpec(ObristModel):
    """Shared package asset copied into each generated Harbor task."""

    source: str
    destination: str


class BenchmarkJobSpec(ObristModel):
    """Single config object that defines a benchmark job and generated tasks."""

    collection_name: str
    job_name: str
    dataset_name: str
    dataset_description: str
    dataset_keywords: tuple[str, ...]
    dataset_author_name: str
    package_dir: Path
    repo_root: Path
    shared_dir: Path
    default_suite: str = "default"
    category: str = "integration"
    profiles: tuple[ProfileSpec, ...]
    cases: tuple[TaskCaseSpec, ...]
    suites: tuple[PackagedSuiteSpec, ...] = Field(default_factory=lambda: (PackagedSuiteSpec(name="default"),))
    environment: EnvironmentDefaults = Field(default_factory=EnvironmentDefaults)
    verifier: VerifierDefaults = Field(default_factory=VerifierDefaults)
    agent: AgentDefaults = Field(default_factory=AgentDefaults)
    output: TypeScriptAppDefaults = Field(default_factory=TypeScriptAppDefaults)
    test_package: NodeTestPackageSpec = Field(default_factory=NodeTestPackageSpec)
    shared_assets: tuple[SharedAssetSpec, ...] = ()
    quality_reward_source: str | None = None
    templates: HarborTemplateOverrides = Field(default_factory=HarborTemplateOverrides)
    execution_constraints: tuple[str, ...] = ()


class PackagedTaskCollectionSpec(ObristModel):
    """Declarative config for a package with `tasks/` and `shared/` directories."""

    name: str
    package_dir: Path
    repo_root: Path
    job_name: str
    default_suite: str = "default"
    task_instruction_template: str = "Run existing benchmark task {task_name}."
    default_dataset_name: str | None = None
    default_dataset_description: str | None = None
    default_dataset_author_name: str = "Obrist"
    suites: tuple[PackagedSuiteSpec, ...] = Field(default_factory=lambda: (PackagedSuiteSpec(name="default"),))


def benchmark_job_collection(spec: BenchmarkJobSpec) -> BenchmarkCollection:
    """Build a collection from a single benchmark job spec."""

    task_names = tuple(_task_name(spec, case, profile) for case in spec.cases for profile in spec.profiles)
    task_slugs = tuple(name.rsplit("/", 1)[-1] for name in task_names)
    tasks = tuple(
        Task(
            name=task_name,
            instructions=f"Run generated benchmark task {task_name}.",
            source_slug=task_slug,
        )
        for task_name, task_slug in zip(task_names, task_slugs, strict=True)
    )
    job = Job(
        name=spec.job_name,
        tasks=tasks,
        dataset_name=spec.dataset_name,
        dataset_description=spec.dataset_description,
        dataset_keywords=spec.dataset_keywords,
        dataset_author_name=spec.dataset_author_name,
        task_name_globs=task_slugs,
    )
    suites = tuple(
        Suite(
            name=suite.name,
            jobs=(job.model_copy(update={"name": suite.job_display_name or job.name}),),
            attempts=suite.attempts,
            agents=suite.agents,
            job_name=suite.job_name,
        )
        for suite in spec.suites
    )
    return BenchmarkCollection(
        name=spec.collection_name,
        suites=suites,
        default_suite=spec.default_suite,
        repo_root=spec.repo_root,
        tasks_dir=spec.package_dir / "tasks",
        shared_dir=spec.shared_dir,
        metadata={"job_spec": spec},
    )


def packaged_task_collection(spec: PackagedTaskCollectionSpec) -> BenchmarkCollection:
    """Build a collection from packaged Harbor-compatible task assets."""

    tasks_dir = spec.package_dir / "tasks"
    shared_dir = spec.package_dir / "shared"
    dataset = _read_toml(tasks_dir / "dataset.toml")
    task_names = _discover_task_names(tasks_dir, dataset)
    task_slugs = tuple(task_name.rsplit("/", 1)[-1] for task_name in task_names)
    tasks = tuple(
        Task(
            name=task_name,
            instructions=spec.task_instruction_template.format(task_name=task_name, task_slug=task_slug),
            source_slug=task_slug,
        )
        for task_name, task_slug in zip(task_names, task_slugs, strict=True)
    )
    job = _packaged_job(spec, dataset, tasks, task_slugs)
    suites = tuple(
        Suite(
            name=suite.name,
            jobs=(job.model_copy(update={"name": suite.job_display_name or job.name}),),
            attempts=suite.attempts,
            agents=suite.agents,
            job_name=suite.job_name,
        )
        for suite in spec.suites
    )
    return BenchmarkCollection(
        name=spec.name,
        suites=suites,
        default_suite=spec.default_suite,
        repo_root=spec.repo_root,
        tasks_dir=tasks_dir,
        shared_dir=shared_dir,
    )


def _packaged_job(
    spec: PackagedTaskCollectionSpec,
    dataset: dict[str, Any],
    tasks: tuple[Task, ...],
    task_slugs: tuple[str, ...],
) -> Job:
    dataset_info = _mapping(dataset.get("dataset"))
    authors = dataset_info.get("authors")
    first_author = authors[0] if isinstance(authors, list) and authors else {}
    author = _mapping(first_author).get("name") or spec.default_dataset_author_name
    return Job(
        name=spec.job_name,
        tasks=tasks,
        dataset_name=str(dataset_info.get("name") or spec.default_dataset_name or spec.name),
        dataset_description=str(
            dataset_info.get("description") or spec.default_dataset_description or f"{spec.name} benchmark"
        ),
        dataset_keywords=tuple(str(keyword) for keyword in dataset_info.get("keywords", ())),
        dataset_author_name=str(author),
        task_name_globs=task_slugs,
    )


def _task_name(spec: BenchmarkJobSpec, case: TaskCaseSpec, profile: ProfileSpec) -> str:
    return f"{spec.dataset_name.rsplit('/', 1)[0]}/{case.slug}-{profile.suffix}"


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as file:
        data = tomllib.load(file)
    if not isinstance(data, dict):
        raise TypeError(f"TOML did not parse as a mapping: {path}")
    return data


def _discover_task_names(tasks_dir: Path, dataset: dict[str, Any]) -> tuple[str, ...]:
    task_entries = dataset.get("tasks")
    if isinstance(task_entries, list):
        manifest_names = tuple(
            str(entry["name"]) for entry in task_entries if isinstance(entry, dict) and "name" in entry
        )
        if manifest_names:
            return manifest_names

    names: list[str] = []
    for task_toml in sorted(tasks_dir.glob("*/task.toml")):
        task_info = _mapping(_read_toml(task_toml).get("task"))
        name = task_info.get("name")
        if name:
            names.append(str(name))
    if not names:
        raise ValueError(f"No benchmark tasks discovered under {tasks_dir}")
    return tuple(names)


def _mapping(value: object) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}
