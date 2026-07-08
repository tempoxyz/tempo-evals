# AUTO-GENERATED FROM shared/docker/main-node/Dockerfile BY npm run sync. DO NOT EDIT MANUALLY.
FROM node:22-trixie

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    python3 \
    python3-pip \
    python3-venv \
  && rm -rf /var/lib/apt/lists/*

COPY rewardkit-package /opt/tempo-bench-rewardkit

RUN python3 -m venv /opt/tempo-bench-rewardkit-venv \
  && /opt/tempo-bench-rewardkit-venv/bin/python -m pip install --no-cache-dir /opt/tempo-bench-rewardkit

ENV tempo_bench_rewardkit_VENV=/opt/tempo-bench-rewardkit-venv

WORKDIR /app
