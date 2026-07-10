#!/usr/bin/env python3
"""Print the immutable base-image tag derived from its build inputs."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
INPUTS = (
    Path("shared/global/docker/base"),
    Path("shared/global/rewardkit-lib"),
    Path("shared/tempo/verifier"),
)


def base_image_repository() -> str:
    image = yaml.safe_load((ROOT / "config/tasks.yaml").read_text())["base_image"]
    return str(image).rsplit(":", maxsplit=1)[0]


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
        file_path = ROOT / name
        if file_path.is_file():
            digest.update(name.encode())
            digest.update(b"\0")
            digest.update(file_path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()[:16]


def source_tag() -> str:
    return f"source-{source_hash()}"


def source_image_ref() -> str:
    return f"{base_image_repository()}:{source_tag()}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("field", choices=["hash", "ref", "tag"])
    args = parser.parse_args()
    value = {
        "hash": source_hash(),
        "ref": source_image_ref(),
        "tag": source_tag(),
    }[args.field]
    print(value)


if __name__ == "__main__":
    main()
