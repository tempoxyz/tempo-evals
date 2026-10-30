FROM public.ecr.aws/docker/library/node@sha256:77d0c7953e80648137a237496c8edbcb3a14bedc5c5298b93a6d0dfa6c3e1271
RUN npm install --global tsx@4.23.1 --no-audit --no-fund
WORKDIR /srv
COPY package.json server.js snapshot.ts shipping.js ./
CMD ["node", "server.js"]
