import json
import os
import re
import subprocess
from pathlib import Path

from rewardkit import criterion

LOG_DIR = Path("/logs/verifier")


def _write_json(name: str, payload: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / name).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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
        ("package_depends_on_viem", "package.json", r'"viem"\s*:'),
        ("source_uses_environment_variables", "src/index.ts", r"process\.env"),
        ("source_uses_address_or_hex_types", "src/index.ts", r"\b(Address|Hex)\b"),
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
