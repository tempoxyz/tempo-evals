// AUTO-GENERATED FROM shared/docs/tempo-docs/server.mjs BY npm run sync. DO NOT EDIT MANUALLY.
import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import path from "node:path";

const port = Number(process.env.PORT ?? "3000");
const docsRoot = path.resolve(process.env.TEMPO_DOCS_ROOT ?? "/tempo-docs");

const contentTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".txt", "text/plain; charset=utf-8"],
  [".md", "text/markdown; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
]);

function aliasRequestPath(requestPath) {
  if (requestPath === "/developers/docs/" || requestPath === "/docs/") return "/developers/docs.md";
  if (requestPath.startsWith("/developers/docs/") && requestPath.endsWith("/")) {
    return requestPath.slice(0, -1);
  }
  if (requestPath.startsWith("/docs/") && requestPath.endsWith("/")) {
    requestPath = requestPath.slice(0, -1);
  }
  if (requestPath === "/") return "/developers";
  if (requestPath === "/llms.txt") return "/developers/llms.txt";
  if (requestPath === "/llms-full.txt") return "/developers/llms-full.txt";
  if (requestPath === "/docs") return "/developers/docs.md";
  if (requestPath.startsWith("/docs/")) return `/developers${requestPath}`;
  return requestPath;
}

function resolveRequestPath(requestPath) {
  const decoded = decodeURIComponent(aliasRequestPath(requestPath));
  const safePath = path.normalize(decoded).replace(/^(\.\.(\/|\\|$))+/, "");
  const absolutePath = path.join(docsRoot, safePath === "/" ? "developers/index.html" : safePath);
  if (!absolutePath.startsWith(docsRoot)) return null;

  if (existsSync(absolutePath)) {
    const stat = statSync(absolutePath);
    if (stat.isDirectory()) {
      const indexPath = path.join(absolutePath, "index.html");
      if (existsSync(indexPath)) return indexPath;
    } else {
      return absolutePath;
    }
  }

  if (!path.extname(absolutePath)) {
    const markdownPath = `${absolutePath}.md`;
    if (existsSync(markdownPath)) return markdownPath;
  }

  const indexPath = path.join(absolutePath, "index.html");
  if (existsSync(indexPath)) return indexPath;
  return null;
}

function sendJson(response, statusCode, value) {
  response.writeHead(statusCode, { "content-type": "application/json; charset=utf-8" });
  response.end(`${JSON.stringify(value)}\n`);
}

const server = createServer((request, response) => {
  const url = new URL(request.url ?? "/", "http://tempo-docs");

  if (url.pathname === "/health") {
    const manifestPath = path.join(docsRoot, "manifest.json");
    const llmsPath = path.join(docsRoot, "developers", "llms.txt");
    sendJson(response, existsSync(llmsPath) ? 200 : 503, {
      ok: existsSync(llmsPath),
      manifest: existsSync(manifestPath) ? "/manifest.json" : null,
    });
    return;
  }

  console.log(`${request.method} ${url.pathname}`);

  if (request.method !== "GET" && request.method !== "HEAD") {
    response.writeHead(405, { "content-type": "text/plain; charset=utf-8" });
    response.end("Method not allowed\n");
    return;
  }

  const filePath = resolveRequestPath(url.pathname);
  if (!filePath || !existsSync(filePath)) {
    response.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    response.end("Not found\n");
    return;
  }

  const contentType = contentTypes.get(path.extname(filePath)) ?? "application/octet-stream";
  response.writeHead(200, { "content-type": contentType });
  if (request.method === "HEAD") {
    response.end();
    return;
  }
  createReadStream(filePath).pipe(response);
});

server.listen(port, (error) => {
  if (error) {
    console.error("Failed to start Tempo docs server:", error);
    process.exit(1);
  }
  console.log(`Tempo docs server serving ${docsRoot} on port ${port}`);
});
