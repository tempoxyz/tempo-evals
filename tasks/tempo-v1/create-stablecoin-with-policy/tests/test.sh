#!/usr/bin/env bash
set -u -o pipefail

LOG_DIR="${TEMPO_BENCH_LOG_DIR:-/logs/verifier}"
WORKSPACE="${TEMPO_BENCH_WORKSPACE:-/app}"
TESTS_DIR="${TEMPO_BENCH_TESTS_DIR:-/tests}"
REWARDKIT_PYTHON="${tempo_bench_rewardkit_VENV:-/opt/tempo-bench-rewardkit-venv}/bin/python"
REWARDKIT_TESTS_DIR="$TESTS_DIR"
REWARDKIT_WORKSPACE="$(mktemp -d)"

mkdir -p "$LOG_DIR"
rm -f "$LOG_DIR/reward.json" "$LOG_DIR/reward-details.json"
trap 'rm -rf "$REWARDKIT_WORKSPACE"' EXIT

write_zero_reward() {
  printf '{"correctness":0,"quality":0,"reward":0}\n' > "$LOG_DIR/reward.json"
}

if ! cp -R "$WORKSPACE/." "$REWARDKIT_WORKSPACE"; then
  write_zero_reward
  exit 0
fi

if ! bash "$TESTS_DIR/correctness/verify-tempo.sh"; then
  write_zero_reward
  exit 0
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -f "$TESTS_DIR/quality/reward.toml" ]; then
  REWARDKIT_TESTS_DIR="$(mktemp -d)"
  cp -R "$TESTS_DIR/." "$REWARDKIT_TESTS_DIR"
  rm -f "$REWARDKIT_TESTS_DIR/quality/reward.toml"
  printf '%s\n' 'Skipping LLM quality reward because ANTHROPIC_API_KEY is not set.' \
    > "$LOG_DIR/quality-skipped.txt"
fi

if [ ! -x "$REWARDKIT_PYTHON" ] || ! "$REWARDKIT_PYTHON" -m rewardkit \
  "$REWARDKIT_TESTS_DIR" --workspace "$REWARDKIT_WORKSPACE"; then
  write_zero_reward
fi
