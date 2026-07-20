#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: $0 <agent-image> <verifier-image>" >&2
  exit 2
fi

agent=$1
verifier=$2

docker run --rm "$agent" sh -ceu '
  for path in /tests /opt/stable-bench/verifier /opt/stable-bench-rewardkit /opt/stable-bench-rewardkit-venv; do
    [ ! -e "$path" ] || { echo "agent image contains $path" >&2; exit 1; }
  done
'
docker run --rm "$verifier" sh -ceu '
  test -d /opt/stable-bench/verifier
  /opt/stable-bench-rewardkit-venv/bin/python -c "import stable_bench_rewardkit"
'

agent_layers=$(docker image inspect "$agent" --format '{{json .RootFS.Layers}}')
verifier_layers=$(docker image inspect "$verifier" --format '{{json .RootFS.Layers}}')
python3 -c 'import json, sys; a, v = map(json.loads, sys.argv[1:]); assert v[:len(a)] == a' \
  "$agent_layers" "$verifier_layers"

echo "Agent/verifier image boundary verified"
