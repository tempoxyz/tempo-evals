import json
import sys
from pathlib import Path


def fail(reason: str) -> None:
    print(reason, file=sys.stderr)
    Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
    Path("/logs/verifier/reward.json").write_text('{"reward":0,"valid_answer":0}\n')
    raise SystemExit(0)


workspace = Path("/app")
expected = json.loads(Path("/tests/expected.json").read_text())
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
    "https://accounts.tempo.xyz/docs/",
    "https://tips.sh/",
)
if not isinstance(sources, list) or not any(
    isinstance(source, str) and source.startswith(tempo_docs_prefixes)
    for source in sources
):
    fail("answer must cite at least one Tempo documentation URL")
lower = text.lower()
if not all(term.lower() in lower for term in expected["terms"]):
    fail("answer is missing required concepts")
Path("/logs/verifier").mkdir(parents=True, exist_ok=True)
Path("/logs/verifier/reward.json").write_text('{"reward":1,"valid_answer":1}\n')
