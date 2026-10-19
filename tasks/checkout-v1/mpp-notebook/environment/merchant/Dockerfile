FROM node:22-trixie
WORKDIR /srv
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY server.ts snapshot.ts ./
CMD ["./node_modules/.bin/tsx", "server.ts"]
