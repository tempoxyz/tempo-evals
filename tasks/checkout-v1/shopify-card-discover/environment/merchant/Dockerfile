FROM mirror.gcr.io/library/node@sha256:77d0c7953e80648137a237496c8edbcb3a14bedc5c5298b93a6d0dfa6c3e1271
RUN npm install --global tsx@4.23.1 --no-audit --no-fund
WORKDIR /srv
COPY package.json ./
RUN npm install --ignore-scripts --no-audit --no-fund
COPY server.ts gateway.ts snapshot.ts shipping.js ./
CMD ["tsx", "server.ts"]
