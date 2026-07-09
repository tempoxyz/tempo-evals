FROM node:22-bookworm

WORKDIR /server

COPY server.mjs ./

ENV PORT=80
ENV HTTPS_PORT=443
ENV TEMPO_DOCS_ROOT=/tempo-docs
ENV TLS_CERT_FILE=/tls/docs.crt
ENV TLS_KEY_FILE=/tls/docs.key
ENV ACCESS_LOG_PATH=/var/log/tempo-docs/access.log

EXPOSE 80 443

CMD ["node", "server.mjs"]
