#!/usr/bin/env bash
set -euo pipefail

solution_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
app_dir="${APP_DIR:-/app}"
mkdir -p "$app_dir"
cp -R "$solution_dir/." "$app_dir/"
rm -f "$app_dir/solve.sh"
