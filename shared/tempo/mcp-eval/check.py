import json
import sys
from pathlib import Path
from urllib.request import urlopen

from validation import has_required_tool_mix, used_data_tools


def fail(reason: str) -> None:
    print(reason, file=sys.stderr)
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/reward.json").write_text('{"reward":0,"valid_answer":0}\n')
    raise SystemExit(0)


workspace = Path("/app")
try:
    answer = json.loads((workspace / "answer.json").read_text())
except (OSError, json.JSONDecodeError):
    fail("answer.json must be valid JSON")

text = answer.get("answer")
sources = answer.get("sources")
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
for tool in used_data_tools(traces[0]):
    if not any(
        isinstance(source, str) and source.startswith(f"mcp://tempo/{tool}")
        for source in sources
    ):
        fail(f"answer must cite used MCP data tool: {tool}")
Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
Path("/logs/verifier/reward.json").write_text('{"reward":1,"valid_answer":1}\n')
