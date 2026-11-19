FROM public.ecr.aws/docker/library/node@sha256:8c761eca2bf7eec965f946cf47b8090143cb41f45f2f8699af0cc0298d2d2d19
WORKDIR /srv
COPY package.json npm-shrinkwrap.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund && ln -s /srv/node_modules/.bin/tsx /usr/local/bin/tsx
COPY server.ts gateway.ts snapshot.ts attempts.ts shipping.js ./
CMD ["./node_modules/.bin/tsx", "server.ts"]
