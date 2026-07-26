"""Image lock-file loading and updates."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

import tomlkit

from evalkit.api import ImageRef

DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


def _valid_digest(value: str) -> bool:
    """Return whether a value is a complete lowercase OCI SHA-256 digest."""
    return DIGEST.fullmatch(value) is not None


def load(path: Path) -> dict[str, str]:
    """Load ``name:tag`` to digest mappings, returning an empty mapping when absent."""
    if not path.exists():
        return {}
    data = tomllib.loads(path.read_text())
    images = data.get("images", {})
    if not isinstance(images, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in images.items()
    ):
        raise ValueError(f"Invalid image lock file: {path}")
    return images


def resolve(image: ImageRef, locks: dict[str, str]) -> str:
    """Return an image's locked digest or reject missing and malformed entries."""
    try:
        digest = locks[image.reference]
    except KeyError as error:
        raise ValueError(f"Image is not locked: {image.reference}") from error
    if not _valid_digest(digest):
        raise ValueError(f"Invalid digest for {image.reference}: {digest}")
    return digest


def inspect_digest(reference: str) -> str:
    """Resolve an image digest using Docker's registry-aware inspector."""
    result = subprocess.run(
        ["docker", "buildx", "imagetools", "inspect", reference],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"^Digest:\s*(sha256:[0-9a-f]{64})$", result.stdout, re.MULTILINE)
    if match is None:
        raise ValueError(f"Docker did not return a digest for {reference}")
    return match.group(1)


def update(path: Path, reference: str, digest: str | None = None) -> str:
    """Update one image lock entry, keeping the TOML output stable."""
    digest = digest or inspect_digest(reference)
    if not _valid_digest(digest):
        raise ValueError(f"Invalid digest: {digest}")
    document = tomlkit.parse(path.read_text()) if path.exists() else tomlkit.document()
    images = document.setdefault("images", tomlkit.table())
    images[reference] = digest
    path.write_text(tomlkit.dumps(document))
    return digest
