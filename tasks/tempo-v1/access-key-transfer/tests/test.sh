#!/usr/bin/env bash
set -u

REWARDKIT_PYTHON="${stable_bench_rewardkit_VENV:-/opt/stable-bench-rewardkit-venv}/bin/python"

if [ ! -x "$REWARDKIT_PYTHON" ]; then
  exit 1
fi
exec "$REWARDKIT_PYTHON" -m stable_bench_rewardkit.tempo.verifier
