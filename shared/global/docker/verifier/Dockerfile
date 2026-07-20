ARG AGENT_IMAGE=stable-bench-agent:local
FROM ${AGENT_IMAGE}

COPY shared/global/rewardkit-lib/pyproject.toml /tmp/stable-bench-rewardkit/pyproject.toml

RUN python3 -m venv /opt/stable-bench-rewardkit-venv \
  && /opt/stable-bench-rewardkit-venv/bin/python -c "import subprocess, sys, tomllib; dependencies = tomllib.load(open('/tmp/stable-bench-rewardkit/pyproject.toml', 'rb'))['project']['dependencies']; subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-cache-dir', *dependencies], check=True)"

COPY shared/global/rewardkit-lib /opt/stable-bench-rewardkit

RUN /opt/stable-bench-rewardkit-venv/bin/python -m pip install --no-cache-dir \
    --no-deps /opt/stable-bench-rewardkit

ENV stable_bench_rewardkit_VENV=/opt/stable-bench-rewardkit-venv

COPY shared/tempo/verifier/package.json shared/tempo/verifier/package-lock.json /opt/stable-bench/verifier/

RUN npm ci --prefix /opt/stable-bench/verifier --no-audit --no-fund

COPY shared/tempo/verifier /opt/stable-bench/verifier
