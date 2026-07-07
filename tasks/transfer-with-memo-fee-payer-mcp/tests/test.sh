#!/usr/bin/env bash
set -u

mkdir -p /logs/verifier
REWARDKIT_VENV="${TEMPO_BENCH_REWARDKIT_VENV:-/tmp/tempo-bench-rewardkit}"
REWARDKIT_PYTHON="$REWARDKIT_VENV/bin/python"
REWARD_FILE="/logs/verifier/reward.json"
DETAILS_FILE="/logs/verifier/reward-details.json"
REWARDKIT_OUTPUT_FILE="/logs/verifier/rewardkit-output.json"
TEMPO_SCORES_FILE="/logs/verifier/tempo-bench-scores.json"
REWARDKIT_TESTS_DIR="/tests"
rm -f "$REWARD_FILE" "$DETAILS_FILE" "$REWARDKIT_OUTPUT_FILE"

skip_llm_quality() {
  reason="$1"
  REWARDKIT_TESTS_DIR="/tmp/tempo-bench-rewardkit-tests"
  rm -rf "$REWARDKIT_TESTS_DIR"
  cp -R /tests "$REWARDKIT_TESTS_DIR"
  rm -f "$REWARDKIT_TESTS_DIR/quality/reward.toml"
  printf '%s\n' "$reason" > /logs/verifier/quality-skipped.txt
}

if [ -z "${ANTHROPIC_API_KEY:-}${ANTHROPIC_AUTH_TOKEN:-}" ] && [ -f /tests/quality/reward.toml ]; then
  skip_llm_quality 'Skipping LLM quality reward because ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN is not set.'
fi

write_binary_reward() {
  python3 - "$DETAILS_FILE" "$TEMPO_SCORES_FILE" "$REWARD_FILE" <<'PY'
import json
import sys
from pathlib import Path

details_path = Path(sys.argv[1])
tempo_scores_path = Path(sys.argv[2])
reward_path = Path(sys.argv[3])
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
elif tempo_scores_path.exists():
    with tempo_scores_path.open(encoding="utf-8") as scores_file:
        scores = json.load(scores_file)
    reward = 1 if int(scores.get("reward", 0)) == 1 else 0

with reward_path.open("w", encoding="utf-8") as reward_file:
    json.dump({"reward": reward}, reward_file, separators=(",", ":"))
    reward_file.write("\n")
PY
}

write_zero_reward() {
  printf '{"reward":0}\n' > "$REWARD_FILE"
}

if [ ! -x "$REWARDKIT_PYTHON" ]; then
  if ! python3 -m venv "$REWARDKIT_VENV" \
    > /logs/verifier/rewardkit-venv.stdout.txt \
    2> /logs/verifier/rewardkit-venv.stderr.txt; then
    write_zero_reward
    exit 0
  fi

  if ! "$REWARDKIT_PYTHON" -m pip install --quiet --no-cache-dir 'harbor-rewardkit==0.1.7' \
    > /logs/verifier/rewardkit-install.stdout.txt \
    2> /logs/verifier/rewardkit-install.stderr.txt; then
    write_zero_reward
    exit 0
  fi
fi

run_rewardkit() {
  "$REWARDKIT_PYTHON" -m rewardkit "$REWARDKIT_TESTS_DIR" \
    --workspace /app \
    --output "$REWARDKIT_OUTPUT_FILE" \
    > /logs/verifier/rewardkit.stdout.txt \
    2> /logs/verifier/rewardkit.stderr.txt
}

if ! run_rewardkit; then
  if [ "$REWARDKIT_TESTS_DIR" = "/tests" ] && [ -f /tests/quality/reward.toml ]; then
    cp /logs/verifier/rewardkit.stderr.txt /logs/verifier/rewardkit-with-llm.stderr.txt
    skip_llm_quality 'Skipping LLM quality reward because the LLM judge failed; reran programmatic rewards only.'
    rm -f "$DETAILS_FILE" "$REWARDKIT_OUTPUT_FILE"
    if ! run_rewardkit; then
      write_binary_reward || write_zero_reward
      exit 0
    fi
  else
    write_binary_reward || write_zero_reward
    exit 0
  fi
fi

write_binary_reward || write_zero_reward

exit 0
