#!/usr/bin/env python3
"""Resolve the paired agent and verifier image references."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
IMAGE_NAMES = ("agent", "verifier")
INPUTS = (
    Path(".dockerignore"),
    Path(".github/workflows/build-images.yml"),
    Path("scripts/images.py"),
    Path("shared/global/docker/agent"),
    Path("shared/global/docker/verifier"),
    Path("shared/global/rewardkit-lib"),
    Path("shared/tempo/verifier"),
)


def configured_image_ref(image: str) -> str:
    images = yaml.safe_load((ROOT / "config/tasks.yaml").read_text())["images"]
    return str(images[image])


def image_repository() -> str:
    repositories = {
        configured_image_ref(image).split("@", maxsplit=1)[0].rsplit(":", 1)[0]
        for image in IMAGE_NAMES
    }
    if len(repositories) != 1:
        raise RuntimeError("Agent and verifier images must share one repository")
    return repositories.pop()


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
        if not path.exists() and not path.is_symlink():
            continue
        mode, content = source_entry(path)
        for value in (name.encode(), mode.encode(), content):
            digest.update(value)
            digest.update(b"\0")
    return digest.hexdigest()


def source_entry(path: Path) -> tuple[str, bytes]:
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode):
        return "120000", os.fsencode(os.readlink(path))
    if stat.S_ISREG(mode):
        return ("100755" if mode & 0o111 else "100644"), path.read_bytes()
    raise RuntimeError(f"Unsupported image source: {path}")


def source_tag(image: str) -> str:
    return f"{image}-source-{source_hash()}"


def source_image_tag(image: str) -> str:
    return f"{image_repository()}:{source_tag(image)}"


def immutable_ref(tagged_ref: str) -> str:
    try:
        result = subprocess.run(
            [
                "docker",
                "buildx",
                "imagetools",
                "inspect",
                tagged_ref,
                "--format",
                "{{.Manifest.Digest}}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"Image is not published: {tagged_ref}") from error
    digest = result.stdout.strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise RuntimeError(f"Invalid registry digest for {tagged_ref}: {digest}")
    return f"{tagged_ref.rsplit(':', 1)[0]}@{digest}"


def source_image_ref(image: str) -> str:
    refs = {name: immutable_ref(source_image_tag(name)) for name in IMAGE_NAMES}
    return refs[image]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("field", choices=["hash", "tag", "repository", "tagged", "ref"])
    parser.add_argument("image", nargs="?", choices=IMAGE_NAMES)
    args = parser.parse_args()
    if args.field in {"tag", "tagged", "ref"} and args.image is None:
        parser.error(f"{args.field} requires an image")
    value = {
        "hash": source_hash,
        "tag": lambda: source_tag(args.image),
        "repository": image_repository,
        "tagged": lambda: source_image_tag(args.image),
        "ref": lambda: source_image_ref(args.image),
    }[args.field]()
    print(value)


if __name__ == "__main__":
    main()
