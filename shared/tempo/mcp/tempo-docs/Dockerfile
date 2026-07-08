FROM node:22-bookworm

WORKDIR /server

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY package.json ./
RUN npm install --omit=dev

COPY server.mjs ./
COPY docs ./docs

EXPOSE 3000

CMD ["node", "server.mjs"]
