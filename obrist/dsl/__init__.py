"""Public Obrist DSL models and grader helpers.

Benchmark packages import from this module to describe read-only collections,
suites, jobs, tasks, runtime tools, sandbox policy, environment policy, and
grader requirements before a backend compiler lowers them to Harbor artifacts.
"""

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

DocsSource = str | Path | None
MappingValue = TypeVar("MappingValue")


def _freeze_mapping(value: Mapping[str, MappingValue] | None) -> Mapping[str, MappingValue]:
    return MappingProxyType(dict(value or {}))


class ObristModel(BaseModel):
    """Strict immutable base model for public Obrist DSL objects."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)


class MCPTransport(StrEnum):
    """Transport protocol used to connect an MCP server to an agent runtime."""

    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable-http"


class EgressMode(StrEnum):
    """Network egress policy requested for a generated task environment."""

    DENY = "deny"
    ALLOWLIST = "allowlist"
    PUBLIC = "public"


class OutputKind(StrEnum):
    """Expected submission artifact shape produced by a task."""

    TS_APP = "ts_app"


class GraderKind(StrEnum):
    """Built-in grader composition and criterion kinds understood by Obrist."""

    FILE_EXISTS = "file_exists"
    FILE_MATCHES = "file_matches"
    SOURCE_PATTERNS = "source_patterns"
    ONCHAIN = "onchain"
    QUALITY_RUBRIC = "quality_rubric"
    ALL_OF = "all_of"
    ANY_OF = "any_of"


class AgentSpec(ObristModel):
    """Agent selection and optional model/environment overrides for a suite run."""

    name: str
    model_name: str | None = None
    env: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("env")
    @classmethod
    def _freeze_env(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        return _freeze_mapping(value)


class MCPServer(ObristModel):
    """MCP server exposed to agents while solving generated benchmark tasks."""

    name: str
    transport: MCPTransport = MCPTransport.STREAMABLE_HTTP
    url: str | None = None
    command: str | None = None
    args: tuple[str, ...] = ()


class Tools(ObristModel):
    """Tooling inputs available to a job, including docs bundles and MCP servers."""

    docs: DocsSource = None
    mcp: tuple[MCPServer, ...] = ()


class Sandbox(ObristModel):
    """Sandbox policy requested for task execution."""

    egress: EgressMode = EgressMode.DENY
    allowed_hosts: tuple[str, ...] = ()


class Env(ObristModel):
    """Environment variable policy for generated tasks."""

    inherit: tuple[str, ...] = ()
    inject: Mapping[str, str] = Field(default_factory=dict)

    @field_validator("inject")
    @classmethod
    def _freeze_inject(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        return _freeze_mapping(value)


class Grader(ObristModel):
    """Opaque grader node produced by DSL helpers and lowered to Harbor."""

    kind: GraderKind
    payload: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("payload")
    @classmethod
    def _freeze_payload(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return _freeze_mapping(value)


class Task(ObristModel):
    """Single benchmark task definition before Harbor compilation."""

    name: str
    instructions: str
    checks: tuple[Grader, ...] = ()
    quality: Grader | None = None
    outputs: OutputKind = OutputKind.TS_APP
    tools: Tools = Field(default_factory=Tools)
    sandbox: Sandbox = Field(default_factory=Sandbox)
    env: Env = Field(default_factory=Env)
    source_slug: str | None = None


class Job(ObristModel):
    """Collection of tasks that should run under the same job-level defaults."""

    name: str
    tasks: tuple[Task, ...]
    docs: DocsSource = None
    sandbox: Sandbox = Field(default_factory=Sandbox)
    env: Env = Field(default_factory=Env)
    dataset_name: str | None = None
    dataset_description: str | None = None
    dataset_keywords: tuple[str, ...] = ()
    dataset_author_name: str | None = None
    task_name_prefix: str = ""
    task_name_globs: tuple[str, ...] = ("*",)


class Suite(ObristModel):
    """Named run configuration for one or more jobs in a collection."""

    name: str
    jobs: tuple[Job, ...]
    attempts: int = 1
    agents: tuple[AgentSpec | str, ...] = ()
    job_name: str | None = None


class BenchmarkCollection(ObristModel):
    """Read-only source package of suites/jobs/tasks for Obrist to compile."""

    name: str
    suites: tuple[Suite, ...]
    default_suite: str
    repo_root: Path
    tasks_dir: Path
    shared_dir: Path
    metadata: Mapping[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _freeze_metadata(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
        return _freeze_mapping(value)

    def suite(self, name: str | None = None) -> Suite:
        """Return a suite by name, or the collection default when omitted."""

        selected = name or self.default_suite
        for suite in self.suites:
            if suite.name == selected:
                return suite
        raise KeyError(f"Unknown suite {selected!r} in collection {self.name!r}")


def file_exists(path: str) -> Grader:
    """Require a submitted artifact path to exist."""

    return Grader(kind=GraderKind.FILE_EXISTS, payload={"path": path})


def file_matches(path: str, pattern: str, name: str | None = None) -> Grader:
    """Require a submitted artifact to match a regular expression."""

    return Grader(kind=GraderKind.FILE_MATCHES, payload={"path": path, "pattern": pattern, "name": name})


def source_patterns(patterns: list[dict[str, str]]) -> Grader:
    """Require source files to match a set of named regular expressions."""

    return Grader(kind=GraderKind.SOURCE_PATTERNS, payload={"patterns": patterns})


def onchain(case: str) -> Grader:
    """Run a domain verifier case against live chain state."""

    return Grader(kind=GraderKind.ONCHAIN, payload={"case": case})


def quality_rubric(criteria: list[dict[str, str]], judge: str = "anthropic/claude-haiku-4-5") -> Grader:
    """Attach a non-binary quality rubric judged outside correctness reward."""

    return Grader(kind=GraderKind.QUALITY_RUBRIC, payload={"criteria": criteria, "judge": judge})


def all_of(*graders: Grader) -> Grader:
    """Compose graders so every child must pass."""

    return Grader(kind=GraderKind.ALL_OF, payload={"graders": graders})


def any_of(*graders: Grader) -> Grader:
    """Compose graders so at least one child must pass."""

    return Grader(kind=GraderKind.ANY_OF, payload={"graders": graders})
