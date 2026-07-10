#!/usr/bin/env python3
"""Print the immutable base-image tag derived from its build inputs."""

from __future__ import annotations

import argparse
import hashlib
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
    for input_path in INPUTS:
        directory = ROOT / input_path
        for file_path in sorted(
            path for path in directory.rglob("*") if path.is_file()
        ):
            digest.update(file_path.relative_to(ROOT).as_posix().encode())
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
