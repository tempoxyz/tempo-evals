#!/usr/bin/env bash
# SYNCED FROM shared/mpp/tests/correctness/verify.sh BY npm run sync. DO NOT EDIT COPIES IN tasks/.
set -u

LOG_DIR="${STABLE_BENCH_LOG_DIR:-/logs/verifier}"
TESTS_DIR="${STABLE_BENCH_TESTS_DIR:-/tests}"
WORKSPACE="${STABLE_BENCH_WORKSPACE:-/app}"
# The venv (pympp + stable-bench-rewardkit) is installed in the stable-bench
# verifier image; see shared/global/docker/verifier/Dockerfile.
VERIFIER_VENV="${stable_bench_rewardkit_VENV:-/opt/stable-bench-rewardkit-venv}"
VERIFIER_PYTHON="$VERIFIER_VENV/bin/python"
SCORES_FILE="$LOG_DIR/scores.json"
WORKSPACE_SCORES_FILE="$WORKSPACE/scores.json"
OUT_FILE="$WORKSPACE/out.json"

mkdir -p "$LOG_DIR"
rm -f "$SCORES_FILE" "$WORKSPACE_SCORES_FILE" "$OUT_FILE"
cd "$WORKSPACE" || exit
rm -rf node_modules

verifier_utils() {
  "$VERIFIER_PYTHON" -m stable_bench_rewardkit.mpp.verifier_utils "$@"
}

write_failure_score() {
  verifier_utils write-failure-score \
    "$SCORES_FILE" "$WORKSPACE_SCORES_FILE" "$LOG_DIR/details.json" "$1"
}

if [ ! -x "$VERIFIER_PYTHON" ]; then
  printf 'missing verifier venv: %s (rebuild the stable-bench verifier image)\n' \
    "$VERIFIER_VENV" >&2
  exit 1
fi

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

verifier_utils check-reward "$SCORES_FILE"
