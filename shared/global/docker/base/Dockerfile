# Shared base image for all tempo-bench task environments (Tempo and MPP).
#
# Bakes in everything the verifiers need so per-task Dockerfiles are just
# `FROM <this image>`:
#   - /opt/tempo-bench-rewardkit-venv: harbor-rewardkit, pympp[tempo], and the
#     tempo-bench-rewardkit package (RewardKit criteria + MPP verifier harness)
#   - /opt/tempo-bench/verifier: the Tempo JS onchain verifier with all cases;
#     the active case is selected at run time via TEMPO_BENCH_CASE
#
# The image reference is pinned as `base_image` in config/tasks.yaml.
# CI publishes it via .github/workflows/build-base-image.yml; local runs
# build it automatically (or run `npm run build-base`). Build context is the
# repo root:
#
#   docker build -t <base_image> -f shared/global/docker/base/Dockerfile .
FROM node:22-trixie

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

COPY shared/global/rewardkit-lib/pyproject.toml /tmp/tempo-bench-rewardkit/pyproject.toml

RUN python3 -m venv /opt/tempo-bench-rewardkit-venv \
  && /opt/tempo-bench-rewardkit-venv/bin/python -c "import subprocess, sys, tomllib; dependencies = tomllib.load(open('/tmp/tempo-bench-rewardkit/pyproject.toml', 'rb'))['project']['dependencies']; subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', *dependencies], check=True)"

COPY shared/global/rewardkit-lib /opt/tempo-bench-rewardkit

RUN /opt/tempo-bench-rewardkit-venv/bin/python -m pip install --no-cache-dir \
    --no-deps /opt/tempo-bench-rewardkit

ENV tempo_bench_rewardkit_VENV=/opt/tempo-bench-rewardkit-venv

COPY shared/tempo/verifier/package.json shared/tempo/verifier/package-lock.json /opt/tempo-bench/verifier/

RUN npm ci --prefix /opt/tempo-bench/verifier --no-audit --no-fund

COPY shared/tempo/verifier /opt/tempo-bench/verifier

WORKDIR /app
