#!/usr/bin/env bash
set -u

REWARDKIT_PYTHON="${tempo_bench_rewardkit_VENV:-/opt/tempo-bench-rewardkit-venv}/bin/python"

if [ ! -x "$REWARDKIT_PYTHON" ]; then
  exit 1
fi
exec "$REWARDKIT_PYTHON" -m tempo_bench_rewardkit.tempo.verifier
