#!/usr/bin/env bash
set -u

LOG_DIR="${TEMPO_BENCH_LOG_DIR:-/logs/verifier}"
ARTIFACT_DIR="${TEMPO_BENCH_ARTIFACT_DIR:-/logs/artifacts}"
INTERNAL_REWARD="$LOG_DIR/tempo-bench-reward.json"
SCORES_FILE="$LOG_DIR/tempo-bench-scores.json"
VERIFIER="${TEMPO_BENCH_VERIFIER:-/opt/tempo-bench/verifier/bin/tempo-bench-verify.js}"

mkdir -p "$LOG_DIR" "$ARTIFACT_DIR"
rm -f "$INTERNAL_REWARD" "$SCORES_FILE"
rm -f "$ARTIFACT_DIR/exception.txt"

write_exception_artifact() {
  phase="$1"
  reason="$2"
  shift 2

  {
    printf 'Tempo verifier failed before producing a passing correctness score.\n'
    printf 'phase: %s\n' "$phase"
    printf 'reason: %s\n' "$reason"
    printf '\nlogs:\n'
    for log_file in "$@"; do
      printf -- '- %s\n' "$log_file"
    done
  } > "$ARTIFACT_DIR/exception.txt"
}

if [ ! -f "$VERIFIER" ]; then
  write_exception_artifact \
    "grader" \
    "missing baked Tempo verifier: $VERIFIER (rebuild the tempo-bench base image)"
  exit 1
fi

cd /app || exit 1
TEMPO_BENCH_INTERNAL_REWARD_FILE="$INTERNAL_REWARD" node "$VERIFIER" \
  > "$LOG_DIR/grader.stdout.txt" \
  2> "$LOG_DIR/grader.stderr.txt"
GRADER_STATUS=$?
printf '{"command":"node","args":["%s"],"status":%d}\n' \
  "$VERIFIER" "$GRADER_STATUS" > "$LOG_DIR/grader.status.json"
if [ "$GRADER_STATUS" -ne 0 ]; then
  write_exception_artifact \
    "grader" \
    "node verifier exited $GRADER_STATUS" \
    "$LOG_DIR/grader.stdout.txt" \
    "$LOG_DIR/grader.stderr.txt" \
    "$LOG_DIR/grader.status.json"
  exit "$GRADER_STATUS"
fi
if [ ! -f "$INTERNAL_REWARD" ]; then
  printf 'missing internal reward file: %s\n' "$INTERNAL_REWARD" >&2
  write_exception_artifact \
    "grader" \
    "missing internal reward file: $INTERNAL_REWARD" \
    "$LOG_DIR/grader.stdout.txt" \
    "$LOG_DIR/grader.stderr.txt" \
    "$LOG_DIR/grader.status.json"
  exit 1
fi

cp "$INTERNAL_REWARD" "$SCORES_FILE"
python3 - "$SCORES_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as score_file:
    scores = json.load(score_file)

sys.exit(0 if float(scores.get("reward", 0)) == 1.0 else 1)
PY
