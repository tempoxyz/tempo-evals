# SYNCED FROM shared/checkout/wallet/link.Dockerfile BY npm run sync. DO NOT EDIT COPIES.
FROM public.ecr.aws/docker/library/node@sha256:8c761eca2bf7eec965f946cf47b8090143cb41f45f2f8699af0cc0298d2d2d19
WORKDIR /srv
COPY link_setup.js ./
CMD ["node", "link_setup.js"]
