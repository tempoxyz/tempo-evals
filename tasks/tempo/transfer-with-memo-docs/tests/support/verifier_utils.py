# SYNCED FROM shared/tempo-testnet/tests/support/verifier_utils.py
# BY npm run sync. DO NOT EDIT COPIES IN tasks/.
import json
import re
import sys
from pathlib import Path

DETAIL_FILES = [
    "scores.json",
    "details.json",
    "reward.json",
    "reward-details.json",
    "verifier-events.ndjson",
    "submission-run.json",
    "submission-output.json",
    "transfer-with-memo-proof.json",
    "transfer-with-memo-failure.json",
    "verify.stdout.txt",
    "verify.stderr.txt",
    "rewardkit.stdout.txt",
    "rewardkit.stderr.txt",
]


def score_of(value: object) -> float:
    if isinstance(value, dict):
        return float(value.get("score", 0))
    if isinstance(value, list):
        return min((score_of(item) for item in value), default=0.0)
    return float(value or 0)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> object | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def redact(text: str) -> str:
    text = re.sub(
        r"(?i)((?:private[_ -]?key|secret|token|authorization)\s*[:=]\s*)\S+",
        r"\1<redacted>",
        text,
    )
    return re.sub(r"(?i)(bearer\s+)\S+", r"\1<redacted>", text)


def write_binary_reward(args: list[str]) -> int:
    details_path = Path(args[0])
    scores_path = Path(args[1])
    reward_path = Path(args[2])
    reward = 0

    scores = read_json(scores_path)
    if isinstance(scores, dict):
        reward = 1 if int(scores.get("reward", 0)) == 1 else 0
    else:
        details = read_json(details_path)
        if isinstance(details, dict):
            reward = 1 if score_of(details.get("correctness", 0)) == 1.0 else 0

    write_json(reward_path, {"reward": reward})
    return 0


def emit_logs(args: list[str]) -> int:
    log_dir = Path(args[0])
    script_status = int(args[1])
    if not log_dir.exists():
        return 0

    files = sorted(path for path in log_dir.iterdir() if path.is_file())
    index = [{"name": path.name, "size": path.stat().st_size} for path in files]
    write_json(log_dir / "log-index.json", index)

    scores = read_json(log_dir / "scores.json")
    scores = scores if isinstance(scores, dict) else {}
    reward = scores.get("reward")
    failed = script_status != 0 or reward != 1

    events_path = log_dir / "verifier-events.ndjson"
    events = []
    if events_path.exists():
        events = events_path.read_text(encoding="utf-8", errors="replace").splitlines()

    summary = {
        "artifactCount": len(index),
        "eventCount": len(events),
        "logIndex": "log-index.json",
        "reason": scores.get("reason"),
        "reward": reward,
        "scriptStatus": script_status,
    }
    print("=== verifier summary ===", flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    if events:
        print("\n=== verifier events tail ===", flush=True)
        for line in events[-8:]:
            print(redact(line), flush=True)

    if not failed:
        return 0

    print("\n=== verifier failure details ===", flush=True)
    for name in DETAIL_FILES:
        path = log_dir / name
        if not path.exists():
            continue
        text = redact(path.read_text(encoding="utf-8", errors="replace"))
        if len(text) > 8000:
            text = text[-8000:]
            print(f"\n=== {name} (tail 8000 chars) ===", flush=True)
        else:
            print(f"\n=== {name} ===", flush=True)
        print(text, end="" if text.endswith("\n") else "\n", flush=True)
    return 0


def write_failure_score(args: list[str]) -> int:
    payload = {"reward": 0, "reason": args[3]}
    for raw_path in args[:3]:
        write_json(Path(raw_path), payload)
    return 0


def check_reward(args: list[str]) -> int:
    scores = read_json(Path(args[0]))
    if not isinstance(scores, dict):
        return 1
    return 0 if float(scores.get("reward", 0)) == 1.0 else 1


COMMANDS = {
    "check-reward": (check_reward, 1),
    "emit-logs": (emit_logs, 2),
    "write-binary-reward": (write_binary_reward, 3),
    "write-failure-score": (write_failure_score, 4),
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"usage: {Path(sys.argv[0]).name} <command> [args...]", file=sys.stderr)
        return 2
    command, args = sys.argv[1], sys.argv[2:]
    handler, arity = COMMANDS[command]
    if len(args) != arity:
        print(f"{command} expects {arity} arguments", file=sys.stderr)
        return 2
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
