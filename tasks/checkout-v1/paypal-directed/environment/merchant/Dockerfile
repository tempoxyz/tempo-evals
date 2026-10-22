FROM node:22-trixie
RUN npm install --global tsx@4.23.1 --no-audit --no-fund
WORKDIR /srv
COPY package.json server.js snapshot.ts shipping.js ./
CMD ["node", "server.js"]
