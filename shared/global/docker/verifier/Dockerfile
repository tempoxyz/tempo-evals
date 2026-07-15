ARG AGENT_IMAGE=ghcr.io/tempoxyz/tempo-bench-agent:v1
FROM ${AGENT_IMAGE}

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
