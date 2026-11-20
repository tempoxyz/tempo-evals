"""Write checkout efficiency baselines from a calibration job.

Usage: uv run python scripts/checkout_baselines.py JOB_DIR [JOB_DIR ...]

Each task's baseline is half the median turns and half the median seconds of
its passing trials, each taken separately: the median keeps one unusually fast
trial from setting it, and halving it makes a typical passing trial score 0.5,
so quality separates good runs from merely typical ones.
A task without a passing trial borrows from its family (the same variant on
other rails, such as mismatch): each peer's baseline is scaled by the median
ratio between the two rails over the families both have measured (those
sharing a tag with the task's family when there are any), and the
task takes the median. A task with no such peer is left out.
Run npm run sync afterwards.
"""

from __future__ import annotations

import json
import statistics
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "shared/checkout/baselines.json"
TASKS = ROOT / "tasks/checkout-v2"
# A typical passing trial is this many baselines of work.
TYPICAL_OVER_BASELINE = 2
FIELDS = {
    "turns": "model_turns",
    "time": "trajectory_duration_sec",
}


def baselines(job_dirs: list[Path]) -> dict[str, dict[str, float]]:
    values: dict[str, dict[str, list[float]]] = {}
    for job in job_dirs:
        for efficiency in sorted(job.glob("*/verifier/efficiency.json")):
            trial = efficiency.parent
            reward = json.loads((trial / "reward.json").read_text())
            metrics = json.loads(efficiency.read_text())
            if reward.get("correctness") != 1 or any(
                f not in metrics for f in FIELDS.values()
            ):
                continue
            result = json.loads((trial.parent / "result.json").read_text())
            task = result["task_name"].split("/", 1)[-1]
            entry = values.setdefault(task, {name: [] for name in FIELDS})
            for name, field in FIELDS.items():
                if metrics[field] > 0:
                    entry[name].append(metrics[field])
    measured = {
        task: {
            name: round(statistics.median(entry[name]) / TYPICAL_OVER_BASELINE, 3)
            for name in FIELDS
        }
        for task, entry in sorted(values.items())
        if all(entry[name] for name in FIELDS)
    }
    return {**family_baselines(measured), **measured}


def task_shapes() -> dict[str, tuple[str, frozenset[str]]]:
    """Map each task to its rail (source task) and family (tags beyond its rail's)."""
    tags: dict[str, dict[str, set[str]]] = {}
    for path in TASKS.glob("*/task.toml"):
        metadata = tomllib.loads(path.read_text())["metadata"]
        rail = tags.setdefault(metadata["source_task"], {})
        rail[path.parent.name] = set(metadata["tags"])
    shapes = {}
    for rail, tasks in tags.items():
        common = set.intersection(*tasks.values())
        for task, task_tags in tasks.items():
            shapes[task] = (rail, frozenset(task_tags - common))
    return shapes


def family_baselines(
    measured: dict[str, dict[str, float]],
    shapes: dict[str, tuple[str, frozenset[str]]] | None = None,
) -> dict[str, dict[str, float]]:
    shapes = task_shapes() if shapes is None else shapes
    rails: dict[str, dict[frozenset[str], dict[str, float]]] = {}
    for task, (rail, family) in shapes.items():
        if task in measured:
            rails.setdefault(rail, {})[family] = measured[task]

    def scaled(value, rail: str, peer_rail: str, family, name: str):
        shared = set(rails.get(rail, {})) & set(rails[peer_rail])
        # Families sharing a tag (mismatch and refuse) compare the rails best.
        shared = {f for f in shared if f & family} or shared
        if not shared:
            return None
        ratio = statistics.median(
            rails[rail][f][name] / rails[peer_rail][f][name] for f in shared
        )
        return value[name] * ratio

    result = {}
    for task, (rail, family) in sorted(shapes.items()):
        if task in measured or not family:
            continue
        peers = [
            (measured[peer], peer_rail)
            for peer, (peer_rail, peer_family) in shapes.items()
            if peer_family == family and peer in measured
        ]
        estimate = {}
        for name in FIELDS:
            values = [scaled(v, rail, r, family, name) for v, r in peers]
            values = [v for v in values if v is not None]
            if values:
                estimate[name] = round(statistics.median(values), 3)
        if len(estimate) == len(FIELDS):
            result[task] = estimate
    return result


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    data = json.loads(BASELINES.read_text())
    data["tasks"] = baselines([Path(arg) for arg in argv])
    BASELINES.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Wrote baselines for {len(data['tasks'])} task(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
