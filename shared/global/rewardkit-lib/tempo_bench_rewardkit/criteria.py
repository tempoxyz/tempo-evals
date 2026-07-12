# Baked into the tempo-bench base image as part of the tempo-bench-rewardkit
# package.
import fcntl
import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from rewardkit import criterion

LOG_DIR = Path(os.environ.get("TEMPO_BENCH_LOG_DIR", "/logs/verifier"))
_EFFICIENCY_LOCK = threading.Lock()

type Cutoff = tuple[int | str, float]
DEFAULT_TOKEN_CUTOFFS: list[Cutoff] = [
    (250000, 1.0),
    (500000, 0.8),
    (1000000, 0.5),
    (1500000, 0.2),
    ("*", 0.0),
]


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


def _parse_cutoffs(raw: str | list[Cutoff]) -> tuple[list[tuple[int, float]], float]:
    cutoffs: list[tuple[int, float]] = []
    fallback = 0.0
    if not isinstance(raw, str):
        for limit, score in raw:
            if limit == "*":
                fallback = float(score)
            else:
                cutoffs.append((int(limit), float(score)))
        return sorted(cutoffs), fallback

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


def _score_by_cutoff(value: int, raw_cutoffs: str | list[Cutoff]) -> float:
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


def _read_workspace_json(workspace: Path, relative_path: str) -> dict[str, Any]:
    return json.loads(_read_workspace_file(workspace, relative_path))


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


NON_TEMPO_BLOCKCHAIN_DEPENDENCIES: frozenset[str] = frozenset(
    (
        "@aptos-labs/ts-sdk",
        "@cardano-sdk/core",
        "@cosmjs/stargate",
        "@hashgraph/sdk",
        "@mysten/sui",
        "@near-js/accounts",
        "@near-js/providers",
        "@polkadot/api",
        "@solana/spl-token",
        "@solana/web3.js",
        "@stacks/transactions",
        "@stellar/stellar-sdk",
        "@ton/core",
        "algosdk",
        "aptos",
        "bitcoinjs-lib",
        "ethers",
        "near-api-js",
        "ripple-lib",
        "sui",
        "tronweb",
        "web3",
        "xrpl",
    )
)
NON_TEMPO_BLOCKCHAIN_NAME_FRAGMENTS: tuple[str, ...] = (
    "algorand",
    "aptos",
    "bitcoin",
    "cardano",
    "cosmos",
    "cosmjs",
    "ethereumjs",
    "ethers",
    "flow",
    "fuel",
    "hashgraph",
    "hedera",
    "metaplex",
    "near",
    "polkadot",
    "solana",
    "starknet",
    "sui",
    "tezos",
    "ton",
    "tron",
    "web3",
    "xrpl",
)
NON_TEMPO_BLOCKCHAIN_SCOPED_PACKAGE_PREFIXES: tuple[str, ...] = (
    "@aptos-labs",
    "@cardano-sdk",
    "@cosmjs",
    "@hashgraph",
    "@mysten",
    "@near-js",
    "@polkadot",
    "@solana",
    "@stacks",
    "@stellar",
    "@ton",
)
NON_TEMPO_BLOCKCHAIN_IMPORT_PATTERN = (
    r"from\s+['\"](?:"
    r"@aptos-labs/|@cardano-sdk/|@cosmjs/|@hashgraph/|@mysten/|@near-js/|"
    r"@polkadot/|@solana/|@stacks/|@stellar/|@ton/|algosdk|aptos|"
    r"bitcoinjs-lib|ethers|fuels|near-api-js|ripple-lib|starknet|sui|"
    r"tronweb|web3|xrpl"
    r")"
    r"|require\(\s*['\"](?:"
    r"@aptos-labs/|@cardano-sdk/|@cosmjs/|@hashgraph/|@mysten/|@near-js/|"
    r"@polkadot/|@solana/|@stacks/|@stellar/|@ton/|algosdk|aptos|"
    r"bitcoinjs-lib|ethers|fuels|near-api-js|ripple-lib|starknet|sui|"
    r"tronweb|web3|xrpl"
    r")"
)


@criterion(shared=True)
def tempo_rejects_other_blockchains(workspace: Path) -> bool:
    try:
        package = _read_workspace_json(workspace, "package.json")
        dependencies = {
            **dict(package.get("dependencies") or {}),
            **dict(package.get("devDependencies") or {}),
        }
        denied_dependencies = sorted(
            name
            for name in dependencies
            if name in NON_TEMPO_BLOCKCHAIN_DEPENDENCIES
            or any(
                fragment in name.lower()
                for fragment in NON_TEMPO_BLOCKCHAIN_NAME_FRAGMENTS
            )
            or any(
                name.startswith(f"{prefix}/")
                for prefix in NON_TEMPO_BLOCKCHAIN_SCOPED_PACKAGE_PREFIXES
            )
        )
        package_error = None
    except Exception as exc:
        denied_dependencies = []
        package_error = str(exc)

    source_check = _pattern_check(
        workspace,
        "source_imports_only_tempo_blockchain_stack",
        "src/index.ts",
        NON_TEMPO_BLOCKCHAIN_IMPORT_PATTERN,
    )
    source_has_denied_import = source_check["passed"]
    results = [
        {
            "name": "dependencies_exclude_other_blockchains",
            "file": "package.json",
            "passed": not denied_dependencies and package_error is None,
            "denied_dependencies": denied_dependencies,
            "error": package_error,
        },
        {
            "name": "source_excludes_other_blockchain_imports",
            "file": "src/index.ts",
            "passed": not source_has_denied_import and source_check["error"] is None,
            "pattern": NON_TEMPO_BLOCKCHAIN_IMPORT_PATTERN,
            "error": source_check["error"],
        },
    ]
    _write_json("tempo-dependency-policy.json", {"checks": results})
    return all(result["passed"] for result in results)


def _uses_viem_tempo(workspace: Path) -> bool:
    patterns = [
        {
            "name": "package_depends_on_viem",
            "file": "package.json",
            "pattern": r'"viem"\s*:',
        },
        {
            "name": "source_imports_viem_tempo",
            "pattern": (
                r"from\s+['\"]viem/tempo(?:/chains)?['\"]|"
                r"require\(\s*['\"]viem/tempo|"
                r"import\(\s*['\"]viem/tempo"
            ),
        },
    ]
    results = [
        _pattern_check(
            workspace,
            str(pattern["name"]),
            str(pattern.get("file", "src/index.ts")),
            str(pattern["pattern"]),
        )
        for pattern in patterns
    ]
    _write_json("tempo-actions.json", {"checks": results})
    return all(result["passed"] for result in results)


@criterion(shared=True)
def tempo_uses_viem_tempo(workspace: Path) -> bool:
    return _uses_viem_tempo(workspace)


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
            "passed": False,
        },
    )
    return False


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
def agent_token_efficiency(
    _workspace: Path,
    cutoffs_env: str = "TEMPO_BENCH_TOKENS_SCORE_CUTOFFS",
    default_cutoffs: list[Cutoff] | None = None,
) -> float:
    """Score agent token usage from trajectory metrics against cutoff thresholds."""
    cutoffs = os.environ.get(cutoffs_env) or default_cutoffs or DEFAULT_TOKEN_CUTOFFS
    path = _trajectory_path()
    if path is None:
        _merge_efficiency(
            "tokens",
            {"score": 0.0, "cutoffs": cutoffs},
        )
        return 0.0

    metrics = _token_metrics(json.loads(path.read_text(encoding="utf-8")))
    # Cached prompt reads repeat prior context across turns; they do not reflect
    # new agent work. Score the uncached estimate while retaining all token
    # totals in the artifact for cost analysis.
    score = _score_by_cutoff(metrics["uncached_token_estimate"], cutoffs)
    _merge_efficiency(
        "tokens",
        {
            "score": score,
            "score_basis": "uncached_token_estimate",
            "cutoffs": cutoffs,
            **metrics,
        },
    )
    return score
