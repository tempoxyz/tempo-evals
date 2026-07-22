FROM node:22-bookworm

WORKDIR /server

COPY server.mjs ./

ENV PORT=80
ENV HTTPS_PORT=443
ENV DOCS_ROOT=/docs
ENV DOCS_INDEX_PATH=/index.html
ENV DOCS_HEALTH_PATH=/llms.txt
ENV DOCS_BASE_URL=https://docs.local
ENV TLS_CERT_FILE=/tls/docs.crt
ENV TLS_KEY_FILE=/tls/docs.key
ENV ACCESS_LOG_PATH=/var/log/docs/access.log

EXPOSE 80 443

CMD ["node", "server.mjs"]
