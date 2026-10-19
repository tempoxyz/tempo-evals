FROM node:22-trixie
WORKDIR /srv
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY pay.ts ./
CMD ["sh", "-c", "mkdir -p /wallet/tools && cp -R node_modules /wallet/tools/node_modules && cp pay.ts /wallet/tools/pay.ts"]
