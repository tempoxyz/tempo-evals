#!/usr/bin/env bash
# SYNCED FROM shared/global/rewardkit/test.sh BY npm run sync. DO NOT EDIT COPIES IN tasks/.
set -u

LOG_DIR="${TEMPO_BENCH_LOG_DIR:-/logs/verifier}"
ARTIFACT_DIR="${TEMPO_BENCH_ARTIFACT_DIR:-/logs/artifacts}"
WORKSPACE="${TEMPO_BENCH_WORKSPACE:-/app}"
TESTS_DIR="${TEMPO_BENCH_TESTS_DIR:-/tests}"

mkdir -p "$LOG_DIR" "$ARTIFACT_DIR"
REWARDKIT_VENV="${tempo_bench_rewardkit_VENV:-/tmp/tempo-bench-rewardkit}"
REWARDKIT_PYTHON="$REWARDKIT_VENV/bin/python"
REWARD_FILE="$LOG_DIR/reward.json"
DETAILS_FILE="$LOG_DIR/reward-details.json"
REWARDKIT_OUTPUT_FILE="$LOG_DIR/rewardkit-output.json"
TEMPO_SCORES_FILE="$LOG_DIR/tempo-bench-scores.json"
REWARDKIT_TESTS_DIR="$TESTS_DIR"
rm -f "$REWARD_FILE" "$DETAILS_FILE" "$REWARDKIT_OUTPUT_FILE"
rm -f "$ARTIFACT_DIR/exception.txt"

write_exception_artifact() {
  phase="$1"
  reason="$2"
  shift 2

  {
    printf 'Tempo task verifier could not produce a passing correctness score.\n'
    printf 'phase: %s\n' "$phase"
    printf 'reason: %s\n' "$reason"
    printf '\nlogs:\n'
    for log_file in "$@"; do
      printf -- '- %s\n' "$log_file"
    done
  } > "$ARTIFACT_DIR/exception.txt"
}

emit_log_file() {
  file_name="$1"
  file_path="$LOG_DIR/$file_name"
  if [ ! -f "$file_path" ]; then
    return
  fi
  printf '\n===== %s =====\n' "$file_name"
  cat "$file_path"
}

emit_harbor_summary() {
  for file_name in \
    verifier-npm-install.stdout.txt \
    verifier-npm-install.status.json \
    grader.stdout.txt \
    grader.status.json \
    tempo-bench-reward.json \
    tempo-bench-scores.json; do
    emit_log_file "$file_name"
  done
  for file_name in \
    verifier-npm-install.stderr.txt \
    grader.stderr.txt; do
    emit_log_file "$file_name" >&2
  done
}

finish() {
  status=$?
  trap - EXIT
  emit_harbor_summary
  exit "$status"
}
trap finish EXIT

skip_llm_quality() {
  reason="$1"
  REWARDKIT_TESTS_DIR="/tmp/tempo-bench-rewardkit-tests"
  rm -rf "$REWARDKIT_TESTS_DIR"
  cp -R "$TESTS_DIR" "$REWARDKIT_TESTS_DIR"
  rm -f "$REWARDKIT_TESTS_DIR/quality/reward.toml"
  printf '%s\n' "$reason" > "$LOG_DIR/quality-skipped.txt"
}

if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -f "$TESTS_DIR/quality/reward.toml" ]; then
  skip_llm_quality 'Skipping LLM quality reward because ANTHROPIC_API_KEY is not set.'
fi

write_binary_reward() {
  python3 - "$DETAILS_FILE" "$TEMPO_SCORES_FILE" "$REWARD_FILE" "$ARTIFACT_DIR/exception.txt" <<'PY'
import json
import sys
from pathlib import Path

details_path = Path(sys.argv[1])
tempo_scores_path = Path(sys.argv[2])
reward_path = Path(sys.argv[3])
exception_path = Path(sys.argv[4])
reward = 0
details = None
scores = None

def score_of(value):
    if isinstance(value, dict):
        return float(value.get("score", 0))
    if isinstance(value, list):
        return min((score_of(item) for item in value), default=0.0)
    return float(value or 0)

def criterion_passed(value, name):
    if isinstance(value, dict):
        if value.get("name") == name:
            raw = value.get("raw", value.get("value", 0))
            if isinstance(raw, bool):
                return raw
            return float(value.get("value", raw or 0)) > 0
        return any(criterion_passed(item, name) for item in value.get("criteria", []))
    if isinstance(value, list):
        return any(criterion_passed(item, name) for item in value)
    return False

def write_exception(reason):
    exception_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "Tempo task verifier produced reward 0.",
        f"reason: {reason}",
        "",
        "logs:",
        f"- {details_path}",
        f"- {tempo_scores_path}",
    ]

    if details:
        lines.append("")
        lines.append(f"correctness score: {score_of(details.get('correctness', 0)):g}")

    if scores:
        lines.append("")
        lines.append(f"tempo scores: {json.dumps(scores, sort_keys=True)}")

    exception_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

if tempo_scores_path.exists():
    with tempo_scores_path.open(encoding="utf-8") as scores_file:
        scores = json.load(scores_file)

if details_path.exists():
    with details_path.open(encoding="utf-8") as details_file:
        details = json.load(details_file)
    correctness = details.get("correctness", 0)
    if criterion_passed(correctness, "tempo_onchain_verifier"):
        reward = score_of(correctness)
elif scores is not None:
    reward = float(scores.get("reward", 0))

with reward_path.open("w", encoding="utf-8") as reward_file:
    json.dump({"reward": reward}, reward_file, separators=(",", ":"))
    reward_file.write("\n")

if reward == 0:
    if details_path.exists():
        write_exception("Tempo onchain verifier criterion did not pass.")
    elif tempo_scores_path.exists():
        write_exception("Tempo onchain verifier reward was below 1.")
    else:
        write_exception("No RewardKit details or Tempo score file was available.")
PY
}

write_zero_reward() {
  printf '{"reward":0}\n' > "$REWARD_FILE"
}

if [ ! -x "$REWARDKIT_PYTHON" ]; then
  if ! python3 -m venv "$REWARDKIT_VENV" \
    > "$LOG_DIR/rewardkit-venv.stdout.txt" \
    2> "$LOG_DIR/rewardkit-venv.stderr.txt"; then
    write_exception_artifact \
      "rewardkit-venv" \
      "python3 -m venv failed" \
      "$LOG_DIR/rewardkit-venv.stdout.txt" \
      "$LOG_DIR/rewardkit-venv.stderr.txt"
    write_zero_reward
    exit 0
  fi

  if ! "$REWARDKIT_PYTHON" -m pip install --quiet --no-cache-dir 'harbor-rewardkit==0.1.7' \
    > "$LOG_DIR/rewardkit-install.stdout.txt" \
    2> "$LOG_DIR/rewardkit-install.stderr.txt"; then
    write_exception_artifact \
      "rewardkit-install" \
      "harbor-rewardkit install failed" \
      "$LOG_DIR/rewardkit-install.stdout.txt" \
      "$LOG_DIR/rewardkit-install.stderr.txt"
    write_zero_reward
    exit 0
  fi
fi

run_rewardkit() {
  "$REWARDKIT_PYTHON" -m rewardkit "$REWARDKIT_TESTS_DIR" \
    --workspace "$WORKSPACE" \
    --output "$REWARDKIT_OUTPUT_FILE" \
    > "$LOG_DIR/rewardkit.stdout.txt" \
    2> "$LOG_DIR/rewardkit.stderr.txt"
}

if ! run_rewardkit; then
  if [ "$REWARDKIT_TESTS_DIR" = "$TESTS_DIR" ] && [ -f "$TESTS_DIR/quality/reward.toml" ]; then
    cp "$LOG_DIR/rewardkit.stderr.txt" "$LOG_DIR/rewardkit-with-llm.stderr.txt"
    skip_llm_quality 'Skipping LLM quality reward because the LLM judge failed; reran programmatic rewards only.'
    rm -f "$DETAILS_FILE" "$REWARDKIT_OUTPUT_FILE"
    if ! run_rewardkit; then
      write_exception_artifact \
        "rewardkit" \
        "RewardKit failed after disabling the LLM quality reward" \
        "$LOG_DIR/rewardkit.stdout.txt" \
        "$LOG_DIR/rewardkit.stderr.txt" \
        "$LOG_DIR/rewardkit-with-llm.stderr.txt"
      write_binary_reward || write_zero_reward
      exit 0
    fi
  else
    write_exception_artifact \
      "rewardkit" \
      "RewardKit failed" \
      "$LOG_DIR/rewardkit.stdout.txt" \
      "$LOG_DIR/rewardkit.stderr.txt"
    write_binary_reward || write_zero_reward
    exit 0
  fi
fi

write_binary_reward || write_zero_reward

exit 0
