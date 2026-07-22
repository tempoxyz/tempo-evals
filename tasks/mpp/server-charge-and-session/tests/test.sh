#!/usr/bin/env bash
# SYNCED FROM shared/mpp/tests/test.sh BY npm run sync. DO NOT EDIT COPIES IN tasks/.
set -u

LOG_DIR="${STABLE_BENCH_LOG_DIR:-/logs/verifier}"
# The venv is installed in the stable-bench verifier image; see
# shared/global/docker/verifier/Dockerfile.
REWARDKIT_VENV="${stable_bench_rewardkit_VENV:-/opt/stable-bench-rewardkit-venv}"
REWARDKIT_PYTHON="$REWARDKIT_VENV/bin/python"
REWARD_FILE="$LOG_DIR/reward.json"
DETAILS_FILE="$LOG_DIR/reward-details.json"
REWARDKIT_OUTPUT_FILE="$LOG_DIR/rewardkit-output.json"
SCORES_FILE="$LOG_DIR/scores.json"
WORKSPACE_SCORES_FILE="${STABLE_BENCH_WORKSPACE:-/app}/scores.json"
OUT_FILE="${STABLE_BENCH_WORKSPACE:-/app}/out.json"
REWARDKIT_TESTS_DIR="${STABLE_BENCH_TESTS_DIR:-/tests}"

mkdir -p "$LOG_DIR"
rm -f "$REWARD_FILE" "$DETAILS_FILE" "$REWARDKIT_OUTPUT_FILE" "$SCORES_FILE" "$WORKSPACE_SCORES_FILE" "$OUT_FILE"

skip_llm_quality() {
  reason="$1"
  REWARDKIT_TESTS_DIR="/tmp/tempo-mpp-rewardkit-tests"
  rm -rf "$REWARDKIT_TESTS_DIR"
  cp -R "${STABLE_BENCH_TESTS_DIR:-/tests}" "$REWARDKIT_TESTS_DIR"
  rm -f "$REWARDKIT_TESTS_DIR/quality/reward.toml"
  printf '%s\n' "$reason" > "$LOG_DIR/quality-skipped.txt"
}

if [ -z "${ANTHROPIC_API_KEY:-}" ] \
  && [ -z "${ANTHROPIC_AUTH_TOKEN:-}" ] \
  && [ -f "${STABLE_BENCH_TESTS_DIR:-/tests}/quality/reward.toml" ]; then
  skip_llm_quality 'Skipping LLM quality reward because no Anthropic judge auth is set.'
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
  export ANTHROPIC_API_KEY="$ANTHROPIC_AUTH_TOKEN"
fi

verifier_utils() {
  "$REWARDKIT_PYTHON" -m stable_bench_rewardkit.mpp.verifier_utils "$@"
}

write_binary_reward() {
  verifier_utils write-binary-reward \
    "$DETAILS_FILE" "$SCORES_FILE" "$REWARDKIT_OUTPUT_FILE" "$REWARD_FILE"
}

write_zero_reward() {
  printf '{"correctness":0,"quality":0,"reward":0}\n' > "$REWARD_FILE"
}

cleanup_mpp_server() {
  verifier_utils cleanup-server "$WORKSPACE_SCORES_FILE" \
    >/dev/null 2>&1
}

emit_verifier_logs() {
  verifier_utils emit-logs "$LOG_DIR" "${1:-0}"
}

finish() {
  status=$?
  trap - EXIT
  cleanup_mpp_server
  emit_verifier_logs "$status"
  exit "$status"
}
trap finish EXIT

if [ ! -x "$REWARDKIT_PYTHON" ]; then
  printf 'missing RewardKit venv: %s (rebuild the stable-bench verifier image)\n' \
    "$REWARDKIT_VENV" >&2
  write_zero_reward
  exit 0
fi

run_rewardkit() {
  "$REWARDKIT_PYTHON" -m rewardkit "$REWARDKIT_TESTS_DIR" \
    --workspace "${STABLE_BENCH_WORKSPACE:-/app}" \
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
    && [ -f "${STABLE_BENCH_TESTS_DIR:-/tests}/quality/reward.toml" ]; then
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
