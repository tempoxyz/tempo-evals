ARG MCP_IMAGE
FROM ${MCP_IMAGE}
USER root
COPY package.json /opt/checkout/
RUN npm install --prefix /opt/checkout --no-audit --no-fund --ignore-scripts
RUN mkdir -p /tmp/.playwright-mcp && chown node:node /tmp/.playwright-mcp
COPY merchant-route.ts session.ts ready.ts browser.json /opt/checkout/
USER node
