import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";

const root = mkdtempSync(path.join(tmpdir(), "tempo-docs-test-"));
const docsRoot = path.join(root, "docs");
mkdirSync(path.join(docsRoot, "developers"), { recursive: true });
writeFileSync(path.join(docsRoot, "manifest.json"), '{"sha":"test-sha"}\n');
writeFileSync(path.join(docsRoot, "developers", "llms.txt"), "Pinned Tempo docs\n");

const upstreamRequests = [];
const upstream = createServer(async (request, response) => {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  upstreamRequests.push({
    method: request.method,
    url: request.url,
    contentType: request.headers["content-type"],
    apiToken: request.headers["x-api-token"],
    host: request.headers.host,
    body: Buffer.concat(chunks).toString(),
  });
  response.writeHead(201, {
    "access-control-allow-origin": "https://tempo.xyz",
    "content-type": "application/json",
    "x-tempo-test": "forwarded",
  });
  response.end('{"ok":true}\n');
});
await new Promise((resolve) => upstream.listen(0, "127.0.0.1", resolve));
const upstreamAddress = upstream.address();

process.env.NODE_ENV = "test";
process.env.TEMPO_DOCS_ROOT = docsRoot;
process.env.ACCESS_LOG_PATH = path.join(root, "access.log");
process.env.TEMPO_API_UPSTREAM_ORIGIN = `http://127.0.0.1:${upstreamAddress.port}`;

const { serveDocs } = await import("./server.mjs");
const sidecar = createServer(serveDocs);
await new Promise((resolve) => sidecar.listen(0, "127.0.0.1", resolve));
const sidecarAddress = sidecar.address();
const sidecarOrigin = `http://127.0.0.1:${sidecarAddress.port}`;

test.after(async () => {
  await Promise.all([
    new Promise((resolve, reject) => sidecar.close((error) => (error ? reject(error) : resolve()))),
    new Promise((resolve, reject) => upstream.close((error) => (error ? reject(error) : resolve()))),
  ]);
  rmSync(root, { recursive: true, force: true });
});

test("proxies Tempo API routes without changing the method, path, query, or body", async () => {
  const response = await fetch(`${sidecarOrigin}/developers/api/faucet?source=benchmark`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-token": "test-token",
    },
    body: '{"address":"0x1234"}',
  });

  assert.equal(response.status, 201);
  assert.equal(response.headers.get("x-tempo-test"), "forwarded");
  assert.equal(response.headers.get("access-control-allow-origin"), "https://tempo.xyz");
  assert.deepEqual(await response.json(), { ok: true });
  assert.deepEqual(upstreamRequests[0], {
    method: "POST",
    url: "/api/faucet?source=benchmark",
    contentType: "application/json",
    apiToken: "test-token",
    host: `127.0.0.1:${upstreamAddress.port}`,
    body: '{"address":"0x1234"}',
  });
});

test("proxies GET requests within the API namespace", async () => {
  const response = await fetch(`${sidecarOrigin}/developers/api/og?size=large`);

  assert.equal(response.status, 201);
  assert.deepEqual(upstreamRequests[1], {
    method: "GET",
    url: "/api/og?size=large",
    contentType: undefined,
    apiToken: undefined,
    host: `127.0.0.1:${upstreamAddress.port}`,
    body: "",
  });
});

test("continues to serve the pinned documentation bundle", async () => {
  const response = await fetch(`${sidecarOrigin}/llms.txt`);
  assert.equal(response.status, 200);
  assert.equal(await response.text(), "Pinned Tempo docs\n");
});

test("does not proxy the API base path or unrelated POST requests", async () => {
  const baseResponse = await fetch(`${sidecarOrigin}/developers/api`);
  assert.equal(baseResponse.status, 404);

  const nearPrefixResponse = await fetch(`${sidecarOrigin}/developers/apiary`);
  assert.equal(nearPrefixResponse.status, 404);

  const docsResponse = await fetch(`${sidecarOrigin}/developers/docs/quickstart`, {
    method: "POST",
  });
  assert.equal(docsResponse.status, 405);
  assert.equal(upstreamRequests.length, 2);
});
