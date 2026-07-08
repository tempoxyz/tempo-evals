FROM node:22-trixie

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    python3 \
    python3-venv \
  && rm -rf /var/lib/apt/lists/*

COPY rewardkit-package /opt/tempo-bench-rewardkit

RUN python3 -m venv /opt/tempo-bench-rewardkit-venv \
  && /opt/tempo-bench-rewardkit-venv/bin/python -m pip install --no-cache-dir /opt/tempo-bench-rewardkit

ENV TEMPO_BENCH_REWARDKIT_VENV=/opt/tempo-bench-rewardkit-venv

WORKDIR /app
