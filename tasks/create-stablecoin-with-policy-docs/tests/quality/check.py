import fcntl
import json
import os
from pathlib import Path

from rewardkit import criterion


def _trajectory_path() -> Path | None:
    for candidate in (
        Path("/logs/trajectory.json"),
        Path("/logs/agent/trajectory.json"),
    ):
        if candidate.exists():
            return candidate
    return None


def _parse_cutoffs(raw: str) -> tuple[list[tuple[int, float]], float]:
    cutoffs: list[tuple[int, float]] = []
    fallback = 0.0
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        limit, separator, score = item.partition("=")
        if not separator:
            raise ValueError(f"Invalid cutoff entry: {item!r}")
        if limit.strip() == "*":
            fallback = float(score)
        else:
            cutoffs.append((int(limit), float(score)))
    return sorted(cutoffs), fallback


def _score_by_cutoff(value: int, raw_cutoffs: str) -> float:
    cutoffs, fallback = _parse_cutoffs(raw_cutoffs)
    for limit, score in cutoffs:
        if value <= limit:
            return score
    return fallback


def _merge_efficiency(section: str, payload: dict) -> None:
    log_path = Path("/logs/verifier/efficiency.json")
    lock_path = Path("/logs/verifier/efficiency.lock")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            metrics = json.loads(log_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            metrics = {}
        metrics[section] = payload
        log_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")


def _token_metrics(trajectory: dict) -> dict[str, int]:
    metrics = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "cached_tokens": 0,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
    }

    for step in trajectory.get("steps", []):
        step_metrics = step.get("metrics") or {}
        metrics["prompt_tokens"] += int(step_metrics.get("prompt_tokens") or 0)
        metrics["completion_tokens"] += int(step_metrics.get("completion_tokens") or 0)
        metrics["cached_tokens"] += int(step_metrics.get("cached_tokens") or 0)
        extra = step_metrics.get("extra") or {}
        metrics["cache_creation_input_tokens"] += int(
            extra.get("cache_creation_input_tokens") or 0
        )
        metrics["cache_read_input_tokens"] += int(
            extra.get("cache_read_input_tokens") or 0
        )

    metrics["total_tokens"] = metrics["prompt_tokens"] + metrics["completion_tokens"]
    metrics["uncached_token_estimate"] = (
        max(metrics["prompt_tokens"] - metrics["cached_tokens"], 0)
        + metrics["completion_tokens"]
    )
    return metrics


@criterion
def agent_turn_efficiency(_workspace: Path) -> float:
    raw_cutoffs = os.environ.get(
        "TEMPO_BENCH_TURNS_SCORE_CUTOFFS",
        "20=1.0,40=0.8,60=0.5,80=0.2,*=0.0",
    )
    path = _trajectory_path()
    if path is None:
        _merge_efficiency(
            "turns",
            {"score": 0.0, "turn_count": None, "cutoffs": raw_cutoffs},
        )
        return 0.0

    trajectory = json.loads(path.read_text(encoding="utf-8"))
    turn_count = sum(
        1 for step in trajectory.get("steps", []) if step.get("source") == "agent"
    )
    score = _score_by_cutoff(turn_count, raw_cutoffs)
    _merge_efficiency(
        "turns",
        {"score": score, "turn_count": turn_count, "cutoffs": raw_cutoffs},
    )
    return score


@criterion
def agent_token_efficiency(_workspace: Path) -> float:
    raw_cutoffs = os.environ.get(
        "TEMPO_BENCH_TOKENS_SCORE_CUTOFFS",
        "250000=1.0,500000=0.8,1000000=0.5,1500000=0.2,*=0.0",
    )
    path = _trajectory_path()
    if path is None:
        _merge_efficiency(
            "tokens",
            {"score": 0.0, "cutoffs": raw_cutoffs},
        )
        return 0.0

    metrics = _token_metrics(json.loads(path.read_text(encoding="utf-8")))
    score = _score_by_cutoff(metrics["total_tokens"], raw_cutoffs)
    _merge_efficiency("tokens", {"score": score, "cutoffs": raw_cutoffs, **metrics})
    return score
