from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from validation import (
    component_reward,
    evidence_summary,
    expected_answer_errors,
    has_required_tool_mix,
    is_tempo_docs_url,
    validated_data_evidence,
)

TRACE_PATHS = {
    "direct": Path("/var/log/tempo-mcp/direct-trace.jsonl"),
    "code": Path("/var/log/tempo-mcp/code-trace.jsonl"),
}


def read_trace(arm: str, path: Path) -> tuple[list[dict], str | None]:
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return [], f"missing {arm} MCP trace artifact: {path}"
    except OSError:
        return [], f"could not read {arm} MCP trace artifact: {path}"

    events = []
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return [], f"malformed {arm} MCP trace JSONL at line {line_number}"
        if not isinstance(event, dict):
            return [], f"malformed {arm} MCP trace JSONL at line {line_number}"
        events.append(event)
    return events, None


def write_result(
    components: dict[str, int],
    errors: list[str],
    warnings: list[str],
    evidence: list[dict],
) -> None:
    log_dir = Path(os.environ.get("STABLE_BENCH_LOG_DIR", "/logs/verifier"))
    log_dir.mkdir(parents=True, exist_ok=True)
    valid_answer = int(not errors)
    reward = component_reward(components)
    (log_dir / "validation.json").write_text(
        json.dumps(
            {
                "components": components,
                "errors": errors,
                "warnings": warnings,
                "trace_backed_data_evidence": evidence,
            }
        )
        + "\n"
    )
    (log_dir / "reward.json").write_text(
        json.dumps(
            {
                "reward": reward,
                "quality": 0,
                "valid_answer": valid_answer,
                **components,
            }
        )
        + "\n"
    )
    if evidence:
        (log_dir / "evidence.json").write_text(
            json.dumps({"evidence": evidence}) + "\n"
        )
    for error in errors:
        print(error, file=sys.stderr)
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)


def main() -> None:
    workspace = Path(os.environ.get("STABLE_BENCH_WORKSPACE", "/app"))
    tests_dir = Path(os.environ.get("STABLE_BENCH_TESTS_DIR", "/tests"))
    components = {
        "schema_valid": 0,
        "docs_source_valid": 0,
        "mcp_tool_mix_valid": 0,
        "data_evidence_valid": 0,
        "task_requirements_valid": 0,
        "quality_judge_available": 0,
    }
    errors: list[str] = []
    warnings: list[str] = []
    validated_evidence: list[dict] = []
    try:
        answer = json.loads((workspace / "answer.json").read_text())
    except (OSError, json.JSONDecodeError):
        answer = {}
        errors.append("answer.json must be valid JSON")
    if not isinstance(answer, dict):
        answer = {}
        errors.append("answer.json must be a JSON object")
    try:
        expected = json.loads((tests_dir / "expected.json").read_text())
    except (OSError, json.JSONDecodeError):
        expected = {}
        errors.append("expected.json must be valid JSON")
    if not isinstance(expected, dict):
        expected = {}
        errors.append("expected.json must be a JSON object")

    summary = answer.get("summary")
    sources = answer.get("sources")
    evidence = answer.get("evidence")
    if not isinstance(summary, str) or not summary.strip():
        errors.append("summary must be a non-empty string")
    if (
        isinstance(summary, str)
        and summary.strip()
        and isinstance(sources, list)
        and isinstance(evidence, list)
    ):
        components["schema_valid"] = 1
    if isinstance(sources, list) and any(
        is_tempo_docs_url(source) for source in sources
    ):
        components["docs_source_valid"] = 1
    else:
        errors.append("answer must cite at least one Tempo documentation URL")

    traces = []
    trace_errors = []
    for arm, path in TRACE_PATHS.items():
        events, error = read_trace(arm, path)
        if error:
            trace_errors.append(error)
        elif events:
            traces.append(events)
    errors.extend(trace_errors)

    if not trace_errors and not traces:
        errors.append("neither MCP arm provided a trace; exactly one must be active")
    elif not trace_errors and len(traces) > 1:
        errors.append("both MCP arms provided traces; exactly one must be active")
    elif not trace_errors and len(traces) == 1:
        trace = traces[0]
        if has_required_tool_mix(trace):
            components["mcp_tool_mix_valid"] = 1
        else:
            errors.append(
                "the active MCP arm must use both a Tempo data tool "
                "and a Tempo docs tool"
            )
        evidence_result = validated_data_evidence(trace, evidence)
        validated_evidence = evidence_result["evidence"]
        errors.extend(evidence_result["errors"])
        warnings.extend(evidence_result["warnings"])
        if validated_evidence:
            components["data_evidence_valid"] = 1
        task_errors = expected_answer_errors(answer, expected, trace)
        if task_errors:
            errors.extend(task_errors)
        else:
            components["task_requirements_valid"] = 1

    write_result(
        components,
        errors,
        warnings,
        evidence_summary(traces[0], validated_evidence) if len(traces) == 1 else [],
    )


if __name__ == "__main__":
    main()
