FROM ghcr.io/tempoxyz/tempo:latest AS tempo

FROM node:22-bookworm

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

COPY --from=tempo /usr/local/bin/tempo /usr/local/bin/tempo

EXPOSE 8545

ENTRYPOINT ["tempo"]
CMD ["node", "--dev", "--http", "--http.addr", "0.0.0.0", "--http.port", "8545", "--http.api", "all", "--ipcdisable", "--disable-discovery", "--disable-auth-server", "--datadir", "/tmp/tempo-dev", "--log.stdout.filter", "info"]
