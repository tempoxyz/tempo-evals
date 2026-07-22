#!/usr/bin/env tsx
import fs from "node:fs";
import http from "node:http";

function usage(): void {
  console.error("Usage: tsx scripts/local-llm-proxy.ts [--env-file PATH]");
}

function loadEnvFile(filePath: string): void {
  for (const line of fs.readFileSync(filePath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const separator = trimmed.indexOf("=");
    if (separator === -1) {
      continue;
    }
    const key = trimmed.slice(0, separator).trim();
    let value = trimmed.slice(separator + 1).trim();
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(key) || process.env[key]) {
      continue;
    }
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    process.env[key] = value;
  }
}

const args = process.argv.slice(2);
for (let index = 0; index < args.length; index += 1) {
  const arg = args[index];
  if (arg === "--env-file") {
    const filePath = args[index + 1];
    if (!filePath) {
      usage();
      process.exit(1);
    }
    loadEnvFile(filePath);
    index += 1;
  } else if (arg === "--help" || arg === "-h") {
    usage();
    process.exit(0);
  } else {
    usage();
    process.exit(1);
  }
}

const listenHost = process.env.LOCAL_LLM_PROXY_LISTEN_HOST ?? "127.0.0.1";
const listenPort = Number(process.env.LOCAL_LLM_PROXY_PORT ?? "19999");
const upstreamHost =
  process.env.LOCAL_LLM_PROXY_UPSTREAM_HOST ??
  process.env.LOCAL_LLM_PROXY_TARGET_HOST;
const upstreamPort = Number(process.env.LOCAL_LLM_PROXY_UPSTREAM_PORT ?? "7891");
const targetHost = process.env.LOCAL_LLM_PROXY_TARGET_HOST ?? upstreamHost;

if (!upstreamHost || !targetHost) {
  console.error(
    "LOCAL_LLM_PROXY_UPSTREAM_HOST or LOCAL_LLM_PROXY_TARGET_HOST is required",
  );
  process.exit(1);
}

const server = http.createServer((request, response) => {
  const upstream = http.request(
    {
      headers: {
        ...request.headers,
        host: `${targetHost}:${upstreamPort}`,
      },
      hostname: upstreamHost,
      method: request.method,
      path: request.url,
      port: upstreamPort,
    },
    (upstreamResponse) => {
      response.writeHead(
        upstreamResponse.statusCode ?? 502,
        upstreamResponse.headers,
      );
      upstreamResponse.pipe(response);
    },
  );

  upstream.on("error", (error) => {
    response.writeHead(502, { "content-type": "application/json" });
    response.end(JSON.stringify({ error: String(error) }));
  });

  request.pipe(upstream);
});

server.listen(listenPort, listenHost, () => {
  console.error(
    `local LLM proxy listening on ${listenHost}:${listenPort} -> ${upstreamHost}:${upstreamPort} as ${targetHost}`,
  );
});
