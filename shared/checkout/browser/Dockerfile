# The task-pinned Playwright MCP image; its tools and schemas stay unchanged.
FROM mcr.microsoft.com/playwright/mcp@sha256:690763cbb437ee7233f538a953bb5390bf03791eb5c965b471e59d17a6132fcb
USER root
COPY package.json npm-shrinkwrap.json /opt/checkout/
RUN npm ci --prefix /opt/checkout --no-audit --no-fund --ignore-scripts
RUN mkdir -p /tmp/.playwright-mcp && chown node:node /tmp/.playwright-mcp
COPY merchant-route.ts session.ts ready.ts browser.json /opt/checkout/
USER node
