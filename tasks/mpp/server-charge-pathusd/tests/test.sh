#!/usr/bin/env bash
set -u

LOG_DIR="${TEMPO_BENCH_LOG_DIR:-/logs/verifier}"
REWARDKIT_VENV="${TEMPO_BENCH_REWARDKIT_VENV:-/tmp/tempo-mpp-rewardkit}"
REWARDKIT_PYTHON="$REWARDKIT_VENV/bin/python"
REWARD_FILE="$LOG_DIR/reward.json"
DETAILS_FILE="$LOG_DIR/reward-details.json"
REWARDKIT_OUTPUT_FILE="$LOG_DIR/rewardkit-output.json"
SCORES_FILE="$LOG_DIR/scores.json"
WORKSPACE_SCORES_FILE="${TEMPO_BENCH_WORKSPACE:-/app}/scores.json"
OUT_FILE="${TEMPO_BENCH_WORKSPACE:-/app}/out.json"
REWARDKIT_TESTS_DIR="${TEMPO_BENCH_TESTS_DIR:-/tests}"
REWARDKIT_PACKAGE_DIR="${TEMPO_BENCH_REWARDKIT_PACKAGE_DIR:-$REWARDKIT_TESTS_DIR/../../../../shared/rewardkit-package}"

mkdir -p "$LOG_DIR"
rm -f "$REWARD_FILE" "$DETAILS_FILE" "$REWARDKIT_OUTPUT_FILE" "$SCORES_FILE" "$WORKSPACE_SCORES_FILE" "$OUT_FILE"

skip_llm_quality() {
  reason="$1"
  REWARDKIT_TESTS_DIR="/tmp/tempo-mpp-rewardkit-tests"
  rm -rf "$REWARDKIT_TESTS_DIR"
  cp -R "${TEMPO_BENCH_TESTS_DIR:-/tests}" "$REWARDKIT_TESTS_DIR"
  rm -f "$REWARDKIT_TESTS_DIR/quality/reward.toml"
  printf '%s\n' "$reason" > "$LOG_DIR/quality-skipped.txt"
}

if [ -z "${ANTHROPIC_API_KEY:-}${ANTHROPIC_AUTH_TOKEN:-}" ] \
  && [ -f "${TEMPO_BENCH_TESTS_DIR:-/tests}/quality/reward.toml" ]; then
  skip_llm_quality 'Skipping LLM quality reward because ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN is not set.'
fi

write_binary_reward() {
  python3 - "$DETAILS_FILE" "$SCORES_FILE" "$REWARD_FILE" <<'PY'
import json
import sys
from pathlib import Path

details_path = Path(sys.argv[1])
scores_path = Path(sys.argv[2])
reward_path = Path(sys.argv[3])
reward = 0

def score_of(value):
    if isinstance(value, dict):
        return float(value.get("score", 0))
    if isinstance(value, list):
        return min((score_of(item) for item in value), default=0.0)
    return float(value or 0)

if scores_path.exists():
    with scores_path.open(encoding="utf-8") as scores_file:
        scores = json.load(scores_file)
    reward = 1 if int(scores.get("reward", 0)) == 1 else 0
elif details_path.exists():
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

cleanup_mpp_server() {
  python3 - "$WORKSPACE_SCORES_FILE" <<'PY' >/dev/null 2>&1
import json
import os
import signal
import sys
import time
from pathlib import Path

scores_path = Path(sys.argv[1])
if not scores_path.exists():
    raise SystemExit(0)

try:
    scores = json.loads(scores_path.read_text(encoding="utf-8"))
    pgid = int(scores.get("server", {}).get("processGroupId", 0))
except Exception:
    raise SystemExit(0)

if pgid <= 0:
    raise SystemExit(0)

for sig in (signal.SIGTERM, signal.SIGKILL):
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        break
    time.sleep(1)
PY
}
trap cleanup_mpp_server EXIT

if [ ! -x "$REWARDKIT_PYTHON" ]; then
  if ! python3 -m venv "$REWARDKIT_VENV" \
    > "$LOG_DIR/rewardkit-venv.stdout.txt" \
    2> "$LOG_DIR/rewardkit-venv.stderr.txt"; then
    write_zero_reward
    exit 0
  fi

  if ! "$REWARDKIT_PYTHON" -m pip install --quiet --no-cache-dir 'harbor-rewardkit==0.1.7' \
    > "$LOG_DIR/rewardkit-install.stdout.txt" \
    2> "$LOG_DIR/rewardkit-install.stderr.txt"; then
    write_zero_reward
    exit 0
  fi
fi

if [ -d "$REWARDKIT_PACKAGE_DIR" ]; then
  "$REWARDKIT_PYTHON" -m pip install --quiet --no-cache-dir "$REWARDKIT_PACKAGE_DIR" \
    > "$LOG_DIR/rewardkit-package-install.stdout.txt" \
    2> "$LOG_DIR/rewardkit-package-install.stderr.txt" || true
fi

if ! "$REWARDKIT_PYTHON" -m pip install --quiet --no-cache-dir 'pympp[tempo]==0.9.1' \
  > "$LOG_DIR/rewardkit-pympp-install.stdout.txt" \
  2> "$LOG_DIR/rewardkit-pympp-install.stderr.txt"; then
  write_zero_reward
  exit 0
fi

run_rewardkit() {
  "$REWARDKIT_PYTHON" -m rewardkit "$REWARDKIT_TESTS_DIR" \
    --workspace "${TEMPO_BENCH_WORKSPACE:-/app}" \
    --output "$REWARDKIT_OUTPUT_FILE" \
    > "$LOG_DIR/rewardkit.stdout.txt" \
    2> "$LOG_DIR/rewardkit.stderr.txt"
}

if ! TEMPO_MPP_KEEP_SERVER=1 bash "$REWARDKIT_TESTS_DIR/correctness/verify.sh" \
  > "$LOG_DIR/verify.stdout.txt" \
  2> "$LOG_DIR/verify.stderr.txt"; then
  printf 'Verifier emitted a failing score; RewardKit will record the score details.\n' \
    > "$LOG_DIR/verify-failed.txt"
fi

if ! run_rewardkit; then
  if [ "$REWARDKIT_TESTS_DIR" != "/tmp/tempo-mpp-rewardkit-tests" ] \
    && [ -f "${TEMPO_BENCH_TESTS_DIR:-/tests}/quality/reward.toml" ]; then
    cp "$LOG_DIR/rewardkit.stderr.txt" "$LOG_DIR/rewardkit-with-llm.stderr.txt"
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
