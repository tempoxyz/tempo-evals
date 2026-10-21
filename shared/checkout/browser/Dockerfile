ARG MCP_IMAGE
FROM ${MCP_IMAGE}
USER root
COPY package.json /opt/checkout/
RUN npm install --prefix /opt/checkout --no-audit --no-fund --ignore-scripts
COPY merchant-route.ts session.ts /opt/checkout/
USER node
