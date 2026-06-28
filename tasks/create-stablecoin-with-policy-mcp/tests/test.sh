#!/usr/bin/env bash
set -u

mkdir -p /logs/verifier
REWARDKIT_VENV="${TEMPO_BENCH_REWARDKIT_VENV:-/tmp/tempo-bench-rewardkit}"
REWARD_FILE="/logs/verifier/reward.json"
DETAILS_FILE="/logs/verifier/reward-details.json"
REWARDKIT_OUTPUT_FILE="/logs/verifier/rewardkit-output.json"
rm -f "$REWARD_FILE" "$DETAILS_FILE" "$REWARDKIT_OUTPUT_FILE"

write_binary_reward() {
  python3 - "$DETAILS_FILE" "$REWARD_FILE" <<'PY'
import json
import sys
from pathlib import Path

details_path = Path(sys.argv[1])
reward_path = Path(sys.argv[2])
reward = 0

def score_of(value):
    if isinstance(value, dict):
        return float(value.get("score", 0))
    if isinstance(value, list):
        return min((score_of(item) for item in value), default=0.0)
    return float(value or 0)

if details_path.exists():
    with details_path.open(encoding="utf-8") as details_file:
        details = json.load(details_file)
    reward = 1 if score_of(details.get("correctness", 0)) == 1.0 else 0

with reward_path.open("w", encoding="utf-8") as reward_file:
    json.dump({"reward": reward}, reward_file, separators=(",", ":"))
    reward_file.write("\n")
PY
}

write_zero_reward() {
  printf '{"reward":0}\n' > "$REWARD_FILE"
}

if ! python3 -m venv "$REWARDKIT_VENV" \
  > /logs/verifier/rewardkit-venv.stdout.txt \
  2> /logs/verifier/rewardkit-venv.stderr.txt; then
  write_zero_reward
  exit 0
fi

if ! "$REWARDKIT_VENV/bin/python" -m pip install --quiet --no-cache-dir 'harbor-rewardkit==0.1.7' \
  > /logs/verifier/rewardkit-install.stdout.txt \
  2> /logs/verifier/rewardkit-install.stderr.txt; then
  write_zero_reward
  exit 0
fi

if ! "$REWARDKIT_VENV/bin/python" -m rewardkit /tests \
  --workspace /app \
  --output "$REWARDKIT_OUTPUT_FILE" \
  > /logs/verifier/rewardkit.stdout.txt \
  2> /logs/verifier/rewardkit.stderr.txt; then
  write_zero_reward
  exit 0
fi

write_binary_reward || write_zero_reward

exit 0
