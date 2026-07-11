import json
import os
import sys
from pathlib import Path
from urllib.request import urlopen

from validation import (
    evidence_summary,
    expected_answer_errors,
    has_required_tool_mix,
    validated_data_evidence,
)


def fail(reason: str) -> None:
    print(reason, file=sys.stderr)
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/reward.json").write_text('{"reward":0,"valid_answer":0}\n')
    raise SystemExit(0)


workspace = Path("/app")
tests_dir = Path(os.environ.get("TEMPO_BENCH_TESTS_DIR", "/tests"))
try:
    answer = json.loads((workspace / "answer.json").read_text())
except (OSError, json.JSONDecodeError):
    fail("answer.json must be valid JSON")
try:
    expected = json.loads((tests_dir / "expected.json").read_text())
except (OSError, json.JSONDecodeError):
    fail("expected.json must be valid JSON")
if not isinstance(expected, dict):
    fail("expected.json must be a JSON object")

text = answer.get("answer")
sources = answer.get("sources")
evidence = answer.get("evidence")
if not isinstance(text, str) or not text.strip():
    fail("answer must be a non-empty string")
tempo_docs_prefixes = (
    "https://docs.tempo.xyz/",
    "https://developers.tempo.xyz/docs/",
    "https://accounts.tempo.xyz/docs/",
    "https://tips.sh/",
)
if not isinstance(sources, list) or not any(
    isinstance(source, str) and source.startswith(tempo_docs_prefixes)
    for source in sources
):
    fail("answer must cite at least one Tempo documentation URL")
try:
    traces = []
    for host in ("tempo-mcp-direct", "tempo-mcp-code"):
        with urlopen(f"http://{host}:8787/trace", timeout=5) as response:  # noqa: S310 -- local task service
            payload = json.loads(response.read())
        events = payload.get("events")
        if isinstance(events, list) and events:
            traces.append(events)
except (OSError, TimeoutError, json.JSONDecodeError):
    fail("could not read MCP bridge traces")

if len(traces) != 1 or not has_required_tool_mix(traces[0]):
    fail("the active MCP arm must use both a Tempo data tool and a Tempo docs tool")
try:
    validated_evidence = validated_data_evidence(traces[0], evidence)
except ValueError as error:
    fail(str(error))
if errors := expected_answer_errors(answer, expected, traces[0]):
    fail("; ".join(errors))
Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
Path("/logs/verifier/evidence.json").write_text(
    json.dumps({"evidence": evidence_summary(traces[0], validated_evidence)}) + "\n"
)
Path("/logs/verifier/reward.json").write_text('{"reward":1,"valid_answer":1}\n')
