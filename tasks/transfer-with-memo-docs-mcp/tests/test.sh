#!/usr/bin/env bash
set -u

mkdir -p /logs/verifier

cd /tests || exit 0

if ! npm install --silent > /logs/verifier/verifier-npm-install.stdout.txt 2> /logs/verifier/verifier-npm-install.stderr.txt; then
  printf '{"reward":0,"onchain":0,"build":0,"run":0}\n' > /logs/verifier/reward.json
  exit 0
fi

node /tests/node_modules/@tempo-bench/verifier/bin/tempo-bench-verify.js > /logs/verifier/grader.stdout.txt 2> /logs/verifier/grader.stderr.txt
exit 0
