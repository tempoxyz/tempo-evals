#!/usr/bin/env bash
set -u -o pipefail

LOG_DIR="${TEMPO_BENCH_LOG_DIR:-/logs/verifier}"
WORKSPACE="${TEMPO_BENCH_WORKSPACE:-/app}"
TESTS_DIR="${TEMPO_BENCH_TESTS_DIR:-/tests}"
REWARDKIT_PYTHON="${tempo_bench_rewardkit_VENV:-/opt/tempo-bench-rewardkit-venv}/bin/python"
JUDGE_WORKSPACE="$(mktemp -d)"

mkdir -p "$LOG_DIR"
trap 'rm -rf "$JUDGE_WORKSPACE"' EXIT

write_failed_reward() {
  python3 - "$LOG_DIR/reward.json" "$1" <<'PY'
import json
import sys
from pathlib import Path

reward_path = Path(sys.argv[1])
reward = json.loads(reward_path.read_text()) if reward_path.exists() else {}
reward.update(
    {
        "reward": 0,
        "quality": 0,
        "valid_answer": 0,
        "quality_judge_available": 0,
        "quality_judge_unavailable": sys.argv[2],
    }
)
reward_path.write_text(json.dumps(reward) + "\n")
PY
}

python3 "$TESTS_DIR/check.py"

if ! python3 - "$LOG_DIR/reward.json" <<'PY'
import json
import sys
from pathlib import Path

score = json.loads(Path(sys.argv[1]).read_text()).get("reward", 0)
raise SystemExit(0 if score == 1 else 1)
PY
then
  exit 0
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  write_failed_reward 'missing_api_key'
  printf '%s\n' 'Failing task because ANTHROPIC_API_KEY is required for MCP quality grading.' \
    > "$LOG_DIR/quality-skipped.txt"
  exit 0
fi

if [ ! -x "$REWARDKIT_PYTHON" ]; then
  write_failed_reward 'missing_rewardkit'
  printf '%s\n' 'Failing task because RewardKit is required for MCP quality grading.' \
    > "$LOG_DIR/quality-skipped.txt"
  exit 0
fi

cp "$WORKSPACE/answer.json" "$JUDGE_WORKSPACE/answer.json" 2>/dev/null || true
cp "$LOG_DIR/evidence.json" "$JUDGE_WORKSPACE/evidence.json" 2>/dev/null || true
cp "$TESTS_DIR/instruction.md" "$JUDGE_WORKSPACE/instruction.md"

if ! (
  cd "$JUDGE_WORKSPACE" || exit 1
  "$REWARDKIT_PYTHON" -m rewardkit "$TESTS_DIR/quality" \
    --workspace "$JUDGE_WORKSPACE" --output "$LOG_DIR/quality-reward.json"
) > "$LOG_DIR/quality-stdout.txt" 2> "$LOG_DIR/quality-stderr.txt"; then
  write_failed_reward 'judge_failed'
  printf '%s\n' 'Failing task because the MCP quality judge failed.' \
    > "$LOG_DIR/quality-skipped.txt"
  exit 0
fi

python3 - "$LOG_DIR/reward.json" "$LOG_DIR/quality-reward.json" <<'PY'
import json
import sys
from pathlib import Path

reward_path = Path(sys.argv[1])
quality_path = Path(sys.argv[2])
reward = json.loads(reward_path.read_text())
quality = json.loads(quality_path.read_text()).get("reward")
if isinstance(quality, int | float):
    reward["quality"] = quality
    reward["quality_judge_available"] = 1
reward_path.write_text(json.dumps(reward) + "\n")
PY
