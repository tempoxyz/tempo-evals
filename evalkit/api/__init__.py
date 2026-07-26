"""Public, typed declarations for evalkit suites."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal

Scope = Literal["agent", "verifier", "runtime"]
"""The task execution context to which an environment value applies."""


def path(value: str | Path) -> PurePosixPath:
    """Create a task-relative POSIX path."""
    result = PurePosixPath(value)
    if result.is_absolute() or ".." in result.parts:
        raise ValueError(f"Task destination must be relative: {value}")
    return result


@dataclass(frozen=True)
class Policy:
    """Suite-wide compiler policy for locks and migration sources."""

    require_image_locks: bool = True
    allow_legacy_sources: bool = True


@dataclass(frozen=True)
class ImageRef:
    """An image name and tag resolved through ``evalkit.lock``."""

    name: str
    tag: str

    @property
    def reference(self) -> str:
        """Return the mutable ``name:tag`` reference resolved through the lock file."""
        return f"{self.name}:{self.tag}"


@dataclass(frozen=True)
class DockerBuild:
    """Image input and files baked into one task environment."""

    image: ImageRef
    assets: tuple[Bake, ...] = ()


@dataclass(frozen=True)
class Environment:
    """Task environments, services, and declared environment variables."""

    agent: DockerBuild | None = None
    verifier: DockerBuild | None = None
    variables: tuple[Env, ...] = ()
    services: tuple[RuntimeService, ...] = ()
    mcps: tuple[RuntimeMCP, ...] = ()


@dataclass(frozen=True)
class Bake:
    """A file or directory copied into an image build context and Docker layer."""

    source: Path
    destination: PurePosixPath
    into: Literal["agent", "verifier"]
    mode: int | None = None


@dataclass(frozen=True)
class Copy:
    """A file or directory copied into a task-relative destination."""

    source: Path
    destination: PurePosixPath


@dataclass(frozen=True)
class Fixture:
    """A named test fixture optionally associated with a schema identifier."""

    source: Path
    name: str
    schema: str | None = None


@dataclass(frozen=True)
class Env:
    """One declared environment variable and its default/forwarding policy."""

    name: str
    forward: bool = True
    default: str | None = None
    required: bool = True
    scope: Scope = "agent"


@dataclass(frozen=True)
class RuntimeService:
    """A Docker sidecar service available while a task runs."""

    name: str
    image: ImageRef
    ports: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)
    command: tuple[str, ...] = ()
    healthcheck: str | None = None
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeMCP:
    """An MCP server injected into the agent environment for one access profile."""

    name: str
    server: str
    access_profile: str
    env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class AdapterContract:
    """Required Python symbols in a task-local verifier adapter."""

    path: PurePosixPath
    symbols: tuple[str, ...]


@dataclass(frozen=True)
class SharedVerifier:
    """Reusable verifier implementation assets and an optional adapter contract."""

    name: str
    source: Path
    contract: AdapterContract | None = None


@dataclass(frozen=True)
class VerifierUse:
    """A task's use of a shared verifier and optional local adapter."""

    verifier: SharedVerifier
    adapter: Path | None = None


@dataclass(frozen=True)
class Case:
    """One named fixture and environment grouping for an explicitly declared case."""

    name: str
    environment: Mapping[str, str] = field(default_factory=dict)
    fixtures: tuple[Fixture, ...] = ()


@dataclass(frozen=True)
class InstructionDoc:
    """Rendered task instruction content and its task-relative destination."""

    content: str
    destination: PurePosixPath = PurePosixPath("instruction.md")


@dataclass(frozen=True)
class Solution:
    """Oracle solution assets and an optional declared entrypoint."""

    assets: tuple[Copy, ...] = ()
    entrypoint: PurePosixPath | None = None


@dataclass(frozen=True)
class Override:
    """An intentional replacement of an otherwise-colliding output asset."""

    destination: PurePosixPath
    reason: str


@dataclass(frozen=True)
class Task:
    """A constrained declaration that compiles to one ordinary Harbor task."""

    name: str
    source: Path | None = None
    aliases: tuple[str, ...] = ()
    copies: tuple[Copy, ...] = ()
    environment: Environment = Environment()
    verifiers: tuple[VerifierUse, ...] = ()
    cases: tuple[Case, ...] = ()
    instruction: InstructionDoc | None = None
    solution: Solution | None = None
    extra_config: Mapping[str, object] = field(default_factory=dict)
    overrides: tuple[Override, ...] = ()


@dataclass(frozen=True)
class Suite:
    """A set of typed task declarations and a Harbor dataset manifest."""

    name: str
    tasks: tuple[Task, ...]
    dataset_source: Path | None = None
    policy: Policy = Policy()


def bake(
    source: str | Path,
    destination: str | Path,
    *,
    into: Literal["agent", "verifier"],
    mode: int | None = None,
) -> Bake:
    """Declare an asset baked into the agent or verifier image at ``destination``."""
    image_destination = PurePosixPath(destination)
    if ".." in image_destination.parts:
        raise ValueError(f"Image destination must not escape its layer: {destination}")
    return Bake(Path(source), image_destination, into, mode)


def copy(source: str | Path, destination: str | Path) -> Copy:
    """Declare a file or directory copy into a task-relative destination."""
    return Copy(Path(source), path(destination))


def fixture(source: str | Path, name: str, schema: str | None = None) -> Fixture:
    """Declare a named fixture copied under the task verifier's fixture directory."""
    return Fixture(Path(source), name, schema)


def env(
    name: str,
    *,
    forward: bool = True,
    default: str | None = None,
    required: bool = True,
    scope: Scope = "agent",
) -> Env:
    """Declare one environment value with explicit default and forwarding behavior."""
    return Env(name, forward, default, required, scope)


def runtime_service(
    name: str,
    image: ImageRef,
    *,
    ports: tuple[str, ...] = (),
    env: Mapping[str, str] | None = None,
    command: tuple[str, ...] = (),
    healthcheck: str | None = None,
    depends_on: tuple[str, ...] = (),
) -> RuntimeService:
    """Declare a runtime Docker sidecar service."""
    return RuntimeService(
        name, image, ports, env or {}, command, healthcheck, depends_on
    )


def runtime_mcp(
    name: str,
    server: str,
    access_profile: str,
    *,
    env: Mapping[str, str] | None = None,
) -> RuntimeMCP:
    """Declare an MCP server and the access profile that enables it."""
    return RuntimeMCP(name, server, access_profile, env or {})


def override(destination: str | Path | Copy | Bake, *, reason: str) -> Override:
    """Allow a destination collision only when the replacement reason is recorded."""
    if not reason:
        raise ValueError("An override requires a reason")
    if isinstance(destination, (Copy, Bake)):
        return Override(destination.destination, reason)
    return Override(path(destination), reason)


def instruction_fragment(*parts: str) -> InstructionDoc:
    """Join non-empty Markdown fragments into a normalized instruction document."""
    return InstructionDoc(
        "\n\n".join(part.strip() for part in parts if part.strip()) + "\n"
    )


__all__ = [
    "AdapterContract",
    "Bake",
    "Case",
    "Copy",
    "DockerBuild",
    "Env",
    "Environment",
    "Fixture",
    "ImageRef",
    "InstructionDoc",
    "Override",
    "Policy",
    "RuntimeMCP",
    "RuntimeService",
    "SharedVerifier",
    "Solution",
    "Suite",
    "Task",
    "VerifierUse",
    "bake",
    "copy",
    "env",
    "fixture",
    "instruction_fragment",
    "override",
    "runtime_mcp",
    "runtime_service",
]
