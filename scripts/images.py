#!/usr/bin/env python3
"""Resolve the paired agent and verifier image references."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IMAGE_NAMES = ("agent", "verifier")
INPUTS = (
    Path(".dockerignore"),
    Path("shared/global/docker/agent"),
    Path("shared/global/docker/verifier"),
    Path("shared/global/rewardkit-lib"),
    Path("shared/tempo/verifier"),
)


def configured_image_ref(image: str) -> str:
    images = yaml.safe_load((ROOT / "config/tasks.yaml").read_text())["images"]
    return str(images[image])


def image_repository(image: str) -> str:
    return configured_image_ref(image).split("@", maxsplit=1)[0].rsplit(":", 1)[0]


def source_hash() -> str:
    digest = hashlib.sha256()
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            *(str(path) for path in INPUTS),
        ],
        check=True,
        cwd=ROOT,
        capture_output=True,
    )
    for name in sorted(filter(None, result.stdout.decode().split("\0"))):
        path = ROOT / name
        if path.is_file():
            digest.update(name.encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()[:16]


def source_tag() -> str:
    return f"source-{source_hash()}"


def source_image_ref(image: str) -> str:
    return f"{image_repository(image)}:{source_tag()}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "field", choices=["hash", "tag", "repository", "ref", "release"]
    )
    parser.add_argument("image", nargs="?", choices=IMAGE_NAMES)
    args = parser.parse_args()
    if args.field in {"repository", "ref", "release"} and args.image is None:
        parser.error(f"{args.field} requires an image")
    value = {
        "hash": source_hash,
        "tag": source_tag,
        "repository": lambda: image_repository(args.image),
        "ref": lambda: source_image_ref(args.image),
        "release": lambda: configured_image_ref(args.image),
    }[args.field]()
    print(value)


if __name__ == "__main__":
    main()
