FROM node:22-trixie

LABEL org.opencontainers.image.source="https://github.com/tempoxyz/tempo-evals"

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    python3 \
    python3-pip \
    python3-venv \
    psmisc \
  && rm -rf /var/lib/apt/lists/*

RUN npm install --global tsx@4.23.1 --no-audit --no-fund

WORKDIR /app
