# AUTO-GENERATED FROM shared/docs/tempo-docs/Dockerfile BY npm run sync. DO NOT EDIT MANUALLY.
FROM node:22-bookworm

WORKDIR /server

COPY server.mjs ./

ENV PORT=3000
ENV TEMPO_DOCS_ROOT=/tempo-docs

EXPOSE 3000

CMD ["node", "server.mjs"]
