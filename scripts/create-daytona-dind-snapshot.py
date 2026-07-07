#!/usr/bin/env python3
"""Create the Daytona DinD snapshot used by the benchmark configs.

This is a small operational helper for config/job.daytona.*.yaml. Keep snapshot
name/resource changes aligned with those configs; do not use this script to
change task packaging or the temporary task staging flow.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from pathlib import Path

from daytona import AsyncDaytona, DaytonaConfig
from daytona.common.sandbox import Resources
from daytona.common.snapshot import CreateSnapshotParams

DEFAULT_NAME = "tempo-bench-dind-28-3-3"
DEFAULT_IMAGE = "docker:28.3.3-dind"


def snapshot_state(snapshot) -> str:
    state = getattr(snapshot, "state", "")
    return str(getattr(state, "value", state)).upper()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and wait for the Daytona DinD snapshot used by Harbor.",
    )
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--target", default=os.environ.get("DAYTONA_TARGET", "us"))
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--cpu", type=int, default=2)
    parser.add_argument("--memory", type=int, default=4, help="Memory in GB.")
    parser.add_argument("--disk", type=int, default=10, help="Disk in GB.")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument(
        "--recreate-error",
        action="store_true",
        help="Delete and recreate the snapshot when it is in an error state.",
    )
    return parser.parse_args()


async def snapshot_by_name(daytona: AsyncDaytona, name: str):
    response = await daytona.snapshot.list()
    snapshots = getattr(response, "items", response)
    for snapshot in snapshots:
        if snapshot.name == name:
            return snapshot
    return None


async def wait_for_snapshot(
    daytona: AsyncDaytona,
    name: str,
    timeout_seconds: int,
):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        snapshot = await snapshot_by_name(daytona, name)
        if snapshot is None:
            await asyncio.sleep(5)
            continue

        state = snapshot_state(snapshot)
        print(f"{name}: {state or 'UNKNOWN'}")
        if state == "ACTIVE":
            return snapshot
        if "ERROR" in state or "FAILED" in state:
            raise RuntimeError(f"Snapshot {name} entered state {state}")
        await asyncio.sleep(10)

    raise TimeoutError(f"Snapshot {name} was not active after {timeout_seconds}s")


async def main() -> None:
    args = parse_args()
    load_env_file(Path(args.env_file))

    if not os.environ.get("DAYTONA_API_KEY"):
        raise SystemExit("DAYTONA_API_KEY is required")

    daytona = AsyncDaytona(DaytonaConfig(target=args.target))
    try:
        existing = await snapshot_by_name(daytona, args.name)
        if existing is not None:
            state = snapshot_state(existing)
            if state == "ACTIVE":
                print(f"snapshot ready: {args.name}")
                return
            if args.recreate_error and ("ERROR" in state or "FAILED" in state):
                await daytona.snapshot.delete(existing)
            else:
                print(f"snapshot exists: {args.name} ({state or 'UNKNOWN'})")
                await wait_for_snapshot(daytona, args.name, args.timeout_seconds)
                print(f"snapshot ready: {args.name}")
                return

        await daytona.snapshot.create(
            CreateSnapshotParams(
                name=args.name,
                image=args.image,
                resources=Resources(
                    cpu=args.cpu,
                    memory=args.memory,
                    disk=args.disk,
                ),
            )
        )
        await wait_for_snapshot(daytona, args.name, args.timeout_seconds)
        print(f"snapshot ready: {args.name}")
    finally:
        await daytona.close()


if __name__ == "__main__":
    asyncio.run(main())
