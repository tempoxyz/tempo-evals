import fcntl
import json
import os
import re
import subprocess
import threading
from pathlib import Path

from rewardkit import criterion

LOG_DIR = Path("/logs/verifier")
_EFFICIENCY_LOCK = threading.Lock()


def _write_json(name: str, payload: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
    log_path = LOG_DIR / "efficiency.json"
    lock_path = LOG_DIR / "efficiency.lock"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with _EFFICIENCY_LOCK, lock_path.open("w", encoding="utf-8") as lock_file:
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


def _read_workspace_file(workspace: Path, relative_path: str) -> str:
    return (workspace / relative_path).read_text(encoding="utf-8")


def _pattern_check(workspace: Path, name: str, file: str, pattern: str) -> dict:
    try:
        content = _read_workspace_file(workspace, file)
        matched = re.search(pattern, content, re.MULTILINE) is not None
        error = None
    except Exception as exc:
        matched = False
        error = str(exc)

    return {
        "name": name,
        "file": file,
        "pattern": pattern,
        "passed": matched,
        "error": error,
    }


@criterion(shared=True)
def tempo_typescript_project(workspace: Path) -> bool:
    file_checks = [
        ("package_json_exists", "package.json"),
        ("tsconfig_json_exists", "tsconfig.json"),
        ("src_index_ts_exists", "src/index.ts"),
    ]
    pattern_checks = [
        ("package_has_build_script", "package.json", r'"build"\s*:'),
        ("package_has_run_script", "package.json", r'"run"\s*:'),
        ("source_uses_environment_variables", "src/index.ts", r"process\.env"),
    ]

    results = []
    for name, relative_path in file_checks:
        exists = (workspace / relative_path).exists()
        results.append(
            {
                "name": name,
                "file": relative_path,
                "passed": exists,
                "error": None if exists else "missing file",
            }
        )

    results.extend(
        _pattern_check(workspace, name, file, pattern)
        for name, file, pattern in pattern_checks
    )

    _write_json("typescript-project.json", {"checks": results})
    return all(result["passed"] for result in results)


@criterion(shared=True)
def tempo_source_patterns(workspace: Path, patterns: list[dict]) -> bool:
    results = [
        _pattern_check(
            workspace,
            str(pattern["name"]),
            str(pattern.get("file", "src/index.ts")),
            str(pattern["pattern"]),
        )
        for pattern in patterns
    ]

    _write_json("source-patterns.json", {"checks": results})
    return all(result["passed"] for result in results)


@criterion(shared=True)
def tempo_onchain_verifier(workspace: Path) -> bool:
    timeout = int(os.environ.get("TEMPO_BENCH_REWARDKIT_TIMEOUT_SECONDS", "900"))
    result = subprocess.run(
        ["bash", "/tests/correctness/verify-tempo.sh"],
        cwd=workspace,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    _write_json(
        "onchain-criterion.json",
        {
            "command": "bash /tests/correctness/verify-tempo.sh",
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
    )
    return result.returncode == 0


@criterion(shared=True)
def tempo_trajectory_matches(_workspace: Path, pattern: str) -> bool:
    for candidate in (
        Path("/logs/trajectory.json"),
        Path("/logs/agent/trajectory.json"),
    ):
        if candidate.exists():
            content = candidate.read_text(encoding="utf-8", errors="replace")
            matched = (
                re.search(pattern, content, re.IGNORECASE | re.MULTILINE) is not None
            )
            _write_json(
                "trajectory-match.json",
                {
                    "trajectory": str(candidate),
                    "pattern": pattern,
                    "passed": matched,
                },
            )
            return matched

    _write_json(
        "trajectory-match.json",
        {
            "trajectory": None,
            "pattern": pattern,
            "passed": True,
        },
    )
    return True


@criterion(shared=True)
def tempo_mcp_tool_used(_workspace: Path, server_name: str = "tempo") -> bool:
    path = _trajectory_path()
    prefix = f"mcp__{server_name}__"
    if path is None:
        _write_json(
            "mcp-tool-use.json",
            {
                "trajectory": None,
                "server_name": server_name,
                "tool_prefix": prefix,
                "tool_calls": [],
                "passed": False,
            },
        )
        return False

    trajectory = json.loads(path.read_text(encoding="utf-8"))
    tool_calls = []
    for step_index, step in enumerate(trajectory.get("steps", [])):
        for call in step.get("tool_calls") or []:
            function_name = call.get("function_name")
            if not isinstance(function_name, str):
                continue
            tool_calls.append(
                {
                    "step_index": step_index,
                    "function_name": function_name,
                    "matched": function_name.startswith(prefix),
                },
            )

    passed = any(call["matched"] for call in tool_calls)
    _write_json(
        "mcp-tool-use.json",
        {
            "trajectory": str(path),
            "server_name": server_name,
            "tool_prefix": prefix,
            "tool_calls": tool_calls,
            "passed": passed,
        },
    )
    return passed


@criterion(shared=True)
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


@criterion(shared=True)
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
