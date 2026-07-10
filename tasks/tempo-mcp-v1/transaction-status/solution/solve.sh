#!/usr/bin/env bash
set -euo pipefail
mkdir -p /app
printf '%s\n' '{"answer":"Tempo transaction submit status guidance.","sources":["https://docs.tempo.xyz/developers"]}' > /app/answer.json
