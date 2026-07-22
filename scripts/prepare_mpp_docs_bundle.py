#!/usr/bin/env python3
"""Prepare a local mpp.dev docs bundle for Harbor task sidecars.

MPP docs already have a real site build pipeline. This script deliberately
stages that built output instead of re-parsing MDX in tempo-evals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path("~/stripe/mpp").expanduser()
DEFAULT_OUTPUT = ROOT / ".cache" / "mpp-docs" / "local" / "public"
BUNDLE_SCHEMA_VERSION = 2


def digest_directory(directory: Path) -> str:
    """Fingerprint the staged docs payload for the eval manifest."""
    digest = hashlib.sha256()
    for path in sorted(p for p in directory.rglob("*") if p.is_file()):
        relative_path = path.relative_to(directory).as_posix()
        if relative_path == "manifest.json":
            continue
        digest.update(relative_path.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def is_prepared(output_root: Path) -> bool:
    """Return whether an eval-ready MPP docs bundle already exists."""
    return (
        (output_root / "manifest.json").exists()
        and (output_root / "llms.txt").exists()
        and (output_root / "llms-full.txt").exists()
        and (output_root / "assets" / "md" / "quickstart" / "server.md").exists()
    )


def is_built_public(public_dir: Path) -> bool:
    """Return whether the MPP checkout has the built docs files we stage."""
    return (
        (public_dir / "llms.txt").exists()
        and (public_dir / "llms-full.txt").exists()
        and (public_dir / "assets" / "md" / "quickstart" / "server.md").exists()
    )


def build_bundle(source: Path, output_root: Path) -> None:
    """Stage built MPP docs output and write eval metadata for the sidecar."""
    public_dir = source / "dist" / "public"
    if not is_built_public(public_dir):
        msg = (
            f"Built MPP docs were not found at {public_dir}. "
            "Run `pnpm build` in the MPP docs checkout first."
        )
        raise RuntimeError(msg)

    shutil.rmtree(output_root, ignore_errors=True)
    shutil.copytree(public_dir, output_root)

    markdown_count = sum(
        1 for path in (output_root / "assets" / "md").rglob("*.md") if path.is_file()
    )
    manifest = {
        "schemaVersion": BUNDLE_SCHEMA_VERSION,
        "docCount": markdown_count,
        "sourceDigest": digest_directory(output_root),
        "publicDir": str(output_root),
        "builtPublicDir": str(public_dir),
        "sourcePath": str(source),
        "routes": {
            "index": "/",
            "llms": "/llms.txt",
            "llmsFull": "/llms-full.txt",
            "markdown": "/assets/md",
        },
    }
    (output_root / "manifest.json").write_text(f"{json.dumps(manifest, indent=2)}\n")


def main() -> None:
    """Parse CLI options and prepare or validate the local bundle."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    output = args.output.resolve()
    if args.check:
        if not is_prepared(output):
            raise RuntimeError("Prepared MPP docs bundle is missing.")
        print(f"Prepared MPP docs bundle is ready at {output}")
        return

    if args.force or not is_prepared(output):
        build_bundle(source, output)
    print(f"Prepared MPP docs bundle is ready at {output}")


if __name__ == "__main__":
    main()
