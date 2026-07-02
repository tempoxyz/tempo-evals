"""Obrist benchmark DSL and compiler framework."""

from pathlib import Path

from obrist.collections import (
    BenchmarkJobSpec,
    EnvironmentDefaults,
    HarborTemplateOverrides,
    NodeTestPackageSpec,
    PackagedSuiteSpec,
    PackagedTaskCollectionSpec,
    ProfileSpec,
    SharedAssetSpec,
    SolutionSpec,
    SourcePatternSpec,
    TaskCaseSpec,
    benchmark_job_collection,
    packaged_task_collection,
)
from obrist.compiler.models import CompileResult
from obrist.dsl import (
    AgentSpec,
    BenchmarkCollection,
    EgressMode,
    Env,
    Grader,
    GraderKind,
    Job,
    MCPTransport,
    ObristModel,
    OutputKind,
    Sandbox,
    Suite,
    Task,
    Tools,
)
from obrist.registry import load_collection as load
from obrist.registry import register


def compile(
    collection: BenchmarkCollection | str,
    *,
    suite: str | None = None,
    out: Path = Path(".generated/obrist"),
) -> CompileResult:
    """Compile a benchmark collection into a generated Harbor workspace."""

    selected_collection = load(collection) if isinstance(collection, str) else collection
    from obrist.backends.harbor.emit import compile_collection

    return compile_collection(selected_collection, suite, out)


__all__ = [
    "AgentSpec",
    "BenchmarkJobSpec",
    "BenchmarkCollection",
    "EgressMode",
    "Env",
    "Grader",
    "GraderKind",
    "Job",
    "MCPTransport",
    "ObristModel",
    "OutputKind",
    "EnvironmentDefaults",
    "HarborTemplateOverrides",
    "NodeTestPackageSpec",
    "PackagedSuiteSpec",
    "PackagedTaskCollectionSpec",
    "ProfileSpec",
    "Sandbox",
    "SharedAssetSpec",
    "SolutionSpec",
    "SourcePatternSpec",
    "Suite",
    "Task",
    "TaskCaseSpec",
    "Tools",
    "benchmark_job_collection",
    "compile",
    "load",
    "packaged_task_collection",
    "register",
]
