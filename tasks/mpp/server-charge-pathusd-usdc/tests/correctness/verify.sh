#!/usr/bin/env bash
set -u

LOG_DIR="${TEMPO_BENCH_LOG_DIR:-/logs/verifier}"
TESTS_DIR="${TEMPO_BENCH_TESTS_DIR:-/tests}"
WORKSPACE="${TEMPO_BENCH_WORKSPACE:-/app}"
VERIFIER_VENV="${TEMPO_MPP_VERIFIER_VENV:-/tmp/tempo-mpp-verifier-venv}"
VERIFIER_PYTHON="$VERIFIER_VENV/bin/python"
SCORES_FILE="$LOG_DIR/scores.json"
WORKSPACE_SCORES_FILE="$WORKSPACE/scores.json"
OUT_FILE="$WORKSPACE/out.json"
VERIFIER_UTILS="$TESTS_DIR/support/verifier_utils.py"

mkdir -p "$LOG_DIR"
rm -f "$SCORES_FILE" "$WORKSPACE_SCORES_FILE" "$OUT_FILE"
cd "$WORKSPACE"
rm -rf node_modules package-lock.json

write_failure_score() {
  python3 "$VERIFIER_UTILS" write-failure-score \
    "$SCORES_FILE" "$WORKSPACE_SCORES_FILE" "$LOG_DIR/details.json" "$1"
}

npm install --silent \
  > "$LOG_DIR/submission-npm-install.stdout.txt" \
  2> "$LOG_DIR/submission-npm-install.stderr.txt"
INSTALL_SUBMISSION_STATUS=$?
printf '{"command":"npm","args":["install","--silent"],"status":%d}\n' \
  "$INSTALL_SUBMISSION_STATUS" > "$LOG_DIR/submission-npm-install.status.json"
if [ "$INSTALL_SUBMISSION_STATUS" -ne 0 ]; then
  write_failure_score "npm install failed"
  exit "$INSTALL_SUBMISSION_STATUS"
fi

npm run build \
  > "$LOG_DIR/submission-build.stdout.txt" \
  2> "$LOG_DIR/submission-build.stderr.txt"
BUILD_STATUS=$?
printf '{"command":"npm","args":["run","build"],"status":%d}\n' \
  "$BUILD_STATUS" > "$LOG_DIR/submission-build.status.json"
if [ "$BUILD_STATUS" -ne 0 ]; then
  write_failure_score "npm run build failed"
  exit "$BUILD_STATUS"
fi

if [ ! -x "$VERIFIER_PYTHON" ]; then
  python3 -m venv "$VERIFIER_VENV" \
    > "$LOG_DIR/verifier-venv.stdout.txt" \
    2> "$LOG_DIR/verifier-venv.stderr.txt"
  VENV_STATUS=$?
  printf '{"command":"python3","args":["-m","venv","%s"],"status":%d}\n' \
    "$VERIFIER_VENV" "$VENV_STATUS" > "$LOG_DIR/verifier-venv.status.json"
  if [ "$VENV_STATUS" -ne 0 ]; then
    write_failure_score "verifier venv setup failed"
    exit "$VENV_STATUS"
  fi
fi

"$VERIFIER_PYTHON" -m pip install --quiet --no-cache-dir 'pympp[tempo]==0.9.1' \
  > "$LOG_DIR/verifier-pip-install.stdout.txt" \
  2> "$LOG_DIR/verifier-pip-install.stderr.txt"
INSTALL_STATUS=$?
printf '{"command":"python","args":["-m","pip","install","pympp[tempo]==0.9.1"],"status":%d}\n' \
  "$INSTALL_STATUS" > "$LOG_DIR/verifier-pip-install.status.json"
if [ "$INSTALL_STATUS" -ne 0 ]; then
  write_failure_score "verifier pympp install failed"
  exit "$INSTALL_STATUS"
fi

"$VERIFIER_PYTHON" "$TESTS_DIR/support/client.py" \
  > "$LOG_DIR/mpp-client.stdout.txt" \
  2> "$LOG_DIR/mpp-client.stderr.txt"
VERIFY_STATUS=$?
printf '{"command":"python","args":["%s"],"status":%d}\n' \
  "$TESTS_DIR/support/client.py" "$VERIFY_STATUS" > "$LOG_DIR/mpp-client.status.json"
if [ "$VERIFY_STATUS" -ne 0 ]; then
  exit "$VERIFY_STATUS"
fi
if [ ! -f "$SCORES_FILE" ]; then
  write_failure_score "verifier did not write scores.json"
  printf 'missing scores file: %s\n' "$SCORES_FILE" >&2
  exit 1
fi

python3 "$VERIFIER_UTILS" check-reward "$SCORES_FILE"
