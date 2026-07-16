from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ZERO_REWARD = {"correctness": 0, "quality": 0, "reward": 0}


def _score(output: dict[str, Any], key: str) -> float:
    value = output.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise ValueError(f"RewardKit output must contain a finite {key} from 0 to 1")
    return round(float(value), 4)


def compose_reward(
    rewardkit_output: dict[str, Any],
) -> dict[str, float | int]:
    # The onchain verifier already passed. Harbor correctness is therefore 1,
    # while RewardKit's code and aggregate scores together form Harbor quality.
    correctness = 1
    code_score = _score(rewardkit_output, "correctness")
    aggregate_quality = _score(rewardkit_output, "quality")
    quality = round((code_score + aggregate_quality) / 2, 4)
    return {
        "correctness": correctness,
        "quality": quality,
        "reward": quality,
    }


def write_reward(
    rewardkit_path: Path,
    output_path: Path,
) -> None:
    rewardkit_output = json.loads(rewardkit_path.read_text())
    if not isinstance(rewardkit_output, dict):
        raise ValueError("RewardKit output must be a JSON object")
    output_path.write_text(f"{json.dumps(compose_reward(rewardkit_output))}\n")
