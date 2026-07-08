# Shared base image for Tempo bench task environments.
#
# It bakes the shared verifier (@tempo-bench/verifier), viem, and tsx into the
# image so each task only ships a small `tests/case.ts`. Build it from the repo
# root before running Harbor:
#
#   docker build -t tempo-bench-base:local -f shared/tempo/docker/tempo-bench-base/Dockerfile .
#
# or: node scripts/build-base.mjs
FROM node:22-bookworm

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl git \
  && rm -rf /var/lib/apt/lists/*

# Build the shared verifier once.
COPY shared/tempo/verifier /opt/tbv/verifier
RUN cd /opt/tbv/verifier \
  && npm install --no-audit --no-fund \
  && npm run build

# Runtime sandbox exposing the verifier + viem + tsx to task case files.
# Task `test.sh` symlinks /tests/node_modules -> here so `case.ts` can
# `import "@tempo-bench/verifier"` and `import "viem"` with normal resolution.
RUN mkdir -p /opt/tbv/runtime \
  && cd /opt/tbv/runtime \
  && printf '{"name":"tbv-runtime","private":true,"dependencies":{"@tempo-bench/verifier":"file:/opt/tbv/verifier","viem":"^2.53.1","tsx":"^4.20.3"}}\n' > package.json \
  && npm install --no-audit --no-fund

WORKDIR /app
