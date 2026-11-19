"""Write checkout efficiency baselines from a calibration job.

Usage: uv run python scripts/checkout_baselines.py JOB_DIR [JOB_DIR ...]

Each task's baseline is the fewest turns and seconds reached by any
passing trial, each taken separately. Tasks without a passing trial are left out
and get no quality score. Run npm run sync afterwards.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINES = ROOT / "shared/checkout/baselines.json"
FIELDS = {
    "turns": "model_turns",
    "time": "trajectory_duration_sec",
}


def baselines(job_dirs: list[Path]) -> dict[str, dict[str, float]]:
    best: dict[str, dict[str, float]] = {}
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
            entry = best.setdefault(task, {})
            for name, field in FIELDS.items():
                value = metrics[field]
                if value > 0 and value < entry.get(name, float("inf")):
                    entry[name] = round(value, 3) if name == "time" else value
    return {
        task: entry for task, entry in sorted(best.items()) if len(entry) == len(FIELDS)
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
