FROM ghcr.io/tempoxyz/tempo:latest AS tempo

FROM node:22-bookworm

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

COPY --from=tempo /usr/local/bin/tempo /usr/local/bin/tempo
COPY tempo-localnet-proxy.mjs /opt/tempo-localnet-proxy/server.mjs

RUN cd /opt/tempo-localnet-proxy \
  && npm init -y >/dev/null \
  && npm install --silent viem@2.53.1

EXPOSE 8545

ENTRYPOINT ["node", "/opt/tempo-localnet-proxy/server.mjs"]
