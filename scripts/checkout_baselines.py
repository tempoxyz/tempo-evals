"""Write checkout efficiency baselines from a calibration job.

Usage: uv run python scripts/checkout_baselines.py JOB_DIR [JOB_DIR ...]

Each task's baseline is the median turns and median seconds of its passing
trials, each taken separately, so one unusually fast trial does not set it.
Tasks without a passing trial are left out and get no quality score.
Run npm run sync afterwards.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "shared/checkout/baselines.json"
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
    return {
        task: {name: round(statistics.median(entry[name]), 3) for name in FIELDS}
        for task, entry in sorted(values.items())
        if all(entry[name] for name in FIELDS)
    }


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
