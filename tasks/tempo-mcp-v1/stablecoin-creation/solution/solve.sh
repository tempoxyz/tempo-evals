#!/usr/bin/env bash
set -euo pipefail
mkdir -p /app
printf '%s\n' '{"answer":"Tempo stablecoin policy create guidance.","sources":["https://docs.tempo.xyz/developers"]}' > /app/answer.json
