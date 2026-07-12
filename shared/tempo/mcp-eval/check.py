import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen

from validation import (
    evidence_summary,
    expected_answer_errors,
    has_required_tool_mix,
    is_tempo_docs_url,
    validated_data_evidence,
)


def write_result(
    components: dict[str, int],
    errors: list[str],
    warnings: list[str],
    evidence: list[dict],
) -> None:
    log_dir = Path(os.environ.get("TEMPO_BENCH_LOG_DIR", "/logs/verifier"))
    log_dir.mkdir(parents=True, exist_ok=True)
    valid_answer = int(not errors)
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
        json.dumps({"reward": valid_answer, "valid_answer": valid_answer, **components})
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


workspace = Path(os.environ.get("TEMPO_BENCH_WORKSPACE", "/app"))
tests_dir = Path(os.environ.get("TEMPO_BENCH_TESTS_DIR", "/tests"))
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

text = answer.get("answer")
sources = answer.get("sources")
evidence = answer.get("evidence")
if not isinstance(text, str) or not text.strip():
    errors.append("answer must be a non-empty string")
if (
    isinstance(text, str)
    and text.strip()
    and isinstance(sources, list)
    and isinstance(evidence, list)
):
    components["schema_valid"] = 1
if isinstance(sources, list) and any(is_tempo_docs_url(source) for source in sources):
    components["docs_source_valid"] = 1
else:
    errors.append("answer must cite at least one Tempo documentation URL")
try:
    trace_path = os.environ.get("TEMPO_BENCH_TRACE_PATH")
    if trace_path:
        payload = json.loads(Path(trace_path).read_text())
        events = payload.get("events")
        traces = [events] if isinstance(events, list) and events else []
    else:
        traces = []
        for host in ("tempo-mcp-direct", "tempo-mcp-code"):
            with urlopen(f"http://{host}:8787/trace", timeout=5) as response:  # noqa: S310 -- local task service
                payload = json.loads(response.read())
            events = payload.get("events")
            if isinstance(events, list) and events:
                traces.append(events)
except (OSError, TimeoutError, json.JSONDecodeError):
    traces = []
    errors.append("could not read MCP bridge traces")

if len(traces) == 1:
    trace = traces[0]
    if has_required_tool_mix(trace):
        components["mcp_tool_mix_valid"] = 1
    else:
        errors.append(
            "the active MCP arm must use both a Tempo data tool and a Tempo docs tool"
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
else:
    errors.append("exactly one active MCP arm must provide a trace")

write_result(
    components,
    errors,
    warnings,
    evidence_summary(traces[0], validated_evidence) if len(traces) == 1 else [],
)
