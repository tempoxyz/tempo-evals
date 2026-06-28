#!/usr/bin/env bash
set -u

mkdir -p /logs/verifier
REWARDKIT_VENV="${TEMPO_BENCH_REWARDKIT_VENV:-/tmp/tempo-bench-rewardkit}"
rm -f /logs/verifier/reward.json

if ! python3 -m venv "$REWARDKIT_VENV" \
  > /logs/verifier/rewardkit-venv.stdout.txt \
  2> /logs/verifier/rewardkit-venv.stderr.txt; then
  printf '{"reward":0}\n' > /logs/verifier/reward.json
  exit 0
fi

if ! "$REWARDKIT_VENV/bin/python" -m pip install --quiet --no-cache-dir 'harbor-rewardkit==0.1.7' \
  > /logs/verifier/rewardkit-install.stdout.txt \
  2> /logs/verifier/rewardkit-install.stderr.txt; then
  printf '{"reward":0}\n' > /logs/verifier/reward.json
  exit 0
fi

if ! "$REWARDKIT_VENV/bin/python" -m rewardkit /tests \
  --workspace /app \
  --output /logs/verifier/reward.json \
  > /logs/verifier/rewardkit.stdout.txt \
  2> /logs/verifier/rewardkit.stderr.txt; then
  printf '{"reward":0}\n' > /logs/verifier/reward.json
fi

exit 0
