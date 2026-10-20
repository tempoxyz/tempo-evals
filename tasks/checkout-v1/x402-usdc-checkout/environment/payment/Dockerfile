FROM node:22-trixie
WORKDIR /srv
COPY package.json ./
RUN npm install --no-audit --no-fund
COPY fund.ts sweep.ts ./
CMD ["./node_modules/.bin/tsx", "fund.ts"]
