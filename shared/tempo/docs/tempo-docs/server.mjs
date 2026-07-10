import {
  appendFileSync,
  createReadStream,
  existsSync,
  mkdirSync,
  readFileSync,
  statSync,
} from "node:fs";
import { createServer as createHttpServer } from "node:http";
import { createServer as createHttpsServer } from "node:https";
import path from "node:path";

const port = Number(process.env.PORT ?? "3000");
const httpsPort = Number(process.env.HTTPS_PORT ?? "443");
const docsRoot = path.resolve(process.env.TEMPO_DOCS_ROOT ?? "/tempo-docs");
const tlsCertFile = process.env.TLS_CERT_FILE ?? "/tls/docs.crt";
const tlsKeyFile = process.env.TLS_KEY_FILE ?? "/tls/docs.key";
const accessLogPath = process.env.ACCESS_LOG_PATH ?? "/var/log/tempo-docs/access.log";

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

function docsSha() {
  try {
    return JSON.parse(readFileSync(path.join(docsRoot, "manifest.json"), "utf8")).sha ?? null;
  } catch {
    return null;
  }
}

function logRequest(request, url) {
  mkdirSync(path.dirname(accessLogPath), { recursive: true });
  appendFileSync(
    accessLogPath,
    `${JSON.stringify({
      host: request.headers.host ?? "",
      method: request.method,
      path: url.pathname,
      query: url.search,
      sha: docsSha(),
    })}\n`,
  );
}

mkdirSync(path.dirname(accessLogPath), { recursive: true });
appendFileSync(accessLogPath, "");

function serveDocs(request, response) {
  const url = new URL(request.url ?? "/", "https://docs.tempo.xyz");

  if (url.pathname === "/health") {
    const manifestPath = path.join(docsRoot, "manifest.json");
    const llmsPath = path.join(docsRoot, "developers", "llms.txt");
    sendJson(response, existsSync(llmsPath) ? 200 : 503, {
      ok: existsSync(llmsPath),
      manifest: existsSync(manifestPath) ? "/manifest.json" : null,
      sha: docsSha(),
    });
    return;
  }

  logRequest(request, url);

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
}

const httpServer = createHttpServer((request, response) => {
  if (new URL(request.url ?? "/", "http://docs.tempo.xyz").pathname === "/health") {
    serveDocs(request, response);
    return;
  }
  const host = (request.headers.host ?? "docs.tempo.xyz").replace(/:80$/, "");
  response.writeHead(308, { location: `https://${host}${request.url ?? "/"}` });
  response.end();
});

const httpsServer = createHttpsServer(
  { cert: readFileSync(tlsCertFile), key: readFileSync(tlsKeyFile) },
  serveDocs,
);

httpServer.listen(port, (error) => {
  if (error) {
    console.error("Failed to start Tempo docs HTTP server:", error);
    process.exit(1);
  }
  console.log(`Tempo docs HTTP server serving ${docsRoot} on port ${port}`);
});

httpsServer.listen(httpsPort, (error) => {
  if (error) {
    console.error("Failed to start Tempo docs HTTPS server:", error);
    process.exit(1);
  }
  console.log(`Tempo docs HTTPS server serving ${docsRoot} on port ${httpsPort}`);
});
