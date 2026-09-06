"""Frozen intermediate representation used by the evalkit compiler."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal

Lifecycle = Literal["build", "runtime", "verifier", "solution"]


@dataclass(frozen=True)
class SourceRef:
    """An immutable asset source backed by a file path or rendered bytes."""

    path: Path | None = None
    content: bytes | None = None

    def read_bytes(self) -> bytes:
        """Return the source bytes, failing if the reference was constructed empty."""
        if self.content is not None:
            return self.content
        if self.path is None:
            raise ValueError("SourceRef has neither path nor content")
        return self.path.read_bytes()


@dataclass(frozen=True)
class Provenance:
    """The declaration responsible for an asset and any recorded replacement reason."""

    declaration: str
    override_reason: str | None = None


@dataclass(frozen=True)
class Asset:
    """One rendered task file with destination, lifecycle, source, and provenance."""

    source: SourceRef
    destination: PurePosixPath
    lifecycle: Lifecycle
    provenance: Provenance
    mode: int | None = None


@dataclass(frozen=True)
class ServiceSpec:
    """Lowered runtime-sidecar configuration independent of the public API types."""

    name: str
    image: str
    ports: tuple[str, ...] = ()
    env: Mapping[str, str] = field(default_factory=dict)
    command: tuple[str, ...] = ()
    healthcheck: str | None = None
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResolvedImage:
    """A mutable image reference paired with its locked immutable digest."""

    reference: str
    digest: str


@dataclass(frozen=True)
class RuntimeDocsSpec:
    """Lowered recipe for materializing one ephemeral documentation bundle."""

    input_name: str
    compose_source: Path
    proxy_source: Path
    bundle_destination: PurePosixPath
    tls_destination: PurePosixPath
    hostname: str
    access_log_source: str
    service: str


@dataclass(frozen=True)
class TaskIR:
    """Complete immutable compiler state for one task before it is rendered."""

    name: str
    slug: str
    aliases: tuple[str, ...]
    assets: tuple[Asset, ...]
    environment: Mapping[str, str]
    services: tuple[ServiceSpec, ...]
    resolved_images: tuple[ResolvedImage, ...]
    image_roles: Mapping[str, str] = field(default_factory=dict)
    runtime_docs: RuntimeDocsSpec | None = None
    source: Path | None = None


@dataclass(frozen=True)
class SuiteIR:
    """Complete immutable compiler state for a suite before it is emitted."""

    name: str
    tasks: tuple[TaskIR, ...]
    dataset_source: Path | None
