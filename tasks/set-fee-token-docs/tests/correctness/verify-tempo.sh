#!/usr/bin/env bash
set -u

LOG_DIR="${TEMPO_BENCH_LOG_DIR:-/logs/verifier}"
INTERNAL_REWARD="$LOG_DIR/tempo-bench-reward.json"
SCORES_FILE="$LOG_DIR/tempo-bench-scores.json"
VERIFIER="/tests/node_modules/@tempo-bench/verifier/bin/tempo-bench-verify.js"

mkdir -p "$LOG_DIR"
rm -f "$INTERNAL_REWARD" "$SCORES_FILE"

cd /tests || exit 1
npm install --silent \
  > "$LOG_DIR/verifier-npm-install.stdout.txt" \
  2> "$LOG_DIR/verifier-npm-install.stderr.txt"
INSTALL_STATUS=$?
printf '{"command":"npm","args":["install","--silent"],"status":%d}\n' \
  "$INSTALL_STATUS" > "$LOG_DIR/verifier-npm-install.status.json"
if [ "$INSTALL_STATUS" -ne 0 ]; then
  exit "$INSTALL_STATUS"
fi

cd /app || exit 1
TEMPO_BENCH_INTERNAL_REWARD_FILE="$INTERNAL_REWARD" node "$VERIFIER" \
  > "$LOG_DIR/grader.stdout.txt" \
  2> "$LOG_DIR/grader.stderr.txt"
GRADER_STATUS=$?
printf '{"command":"node","args":["%s"],"status":%d}\n' \
  "$VERIFIER" "$GRADER_STATUS" > "$LOG_DIR/grader.status.json"
if [ "$GRADER_STATUS" -ne 0 ]; then
  exit "$GRADER_STATUS"
fi
if [ ! -f "$INTERNAL_REWARD" ]; then
  printf 'missing internal reward file: %s\n' "$INTERNAL_REWARD" >&2
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
