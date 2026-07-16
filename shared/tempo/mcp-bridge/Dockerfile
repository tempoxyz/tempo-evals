FROM node:22-bookworm-slim
WORKDIR /bridge
RUN npm install --global tsx@4.23.1 --no-audit --no-fund
COPY server.ts ./
CMD ["tsx", "server.ts"]
