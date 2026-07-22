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

const port = Number(process.env.PORT ?? "80");
const httpsPort = Number(process.env.HTTPS_PORT ?? "443");
const docsRoot = path.resolve(
  process.env.DOCS_ROOT ??
    process.env.TEMPO_DOCS_ROOT ??
    process.env.MPP_DOCS_ROOT ??
    "/docs",
);
const indexPath = process.env.DOCS_INDEX_PATH ?? "/index.html";
const healthPath = process.env.DOCS_HEALTH_PATH ?? "/llms.txt";
const baseUrl = process.env.DOCS_BASE_URL ?? "https://docs.local";
const markdownAliasPrefix = process.env.DOCS_MARKDOWN_ALIAS_PREFIX ?? "";
const tlsCertFile = process.env.TLS_CERT_FILE ?? "/tls/docs.crt";
const tlsKeyFile = process.env.TLS_KEY_FILE ?? "/tls/docs.key";
const accessLogPath = process.env.ACCESS_LOG_PATH ?? "/var/log/docs/access.log";
const siteName = process.env.DOCS_SITE_NAME ?? "docs";

const exactAliases = parseJsonEnv("DOCS_EXACT_ALIASES", {});
const prefixAliases = parseJsonEnv("DOCS_PREFIX_ALIASES", []);
const stripTrailingSlashPrefixes = parseJsonEnv(
  "DOCS_STRIP_TRAILING_SLASH_PREFIXES",
  [],
);

const contentTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".txt", "text/plain; charset=utf-8"],
  [".md", "text/markdown; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
]);

function parseJsonEnv(name, fallback) {
  const raw = process.env[name];
  if (!raw) return fallback;
  try {
    return JSON.parse(raw);
  } catch (error) {
    console.error(`Invalid ${name}:`, error);
    process.exit(1);
  }
}

function aliasRequestPath(requestPath) {
  if (Object.hasOwn(exactAliases, requestPath)) return exactAliases[requestPath];

  for (const prefix of stripTrailingSlashPrefixes) {
    if (requestPath.startsWith(prefix) && requestPath.endsWith("/")) {
      requestPath = requestPath.slice(0, -1);
      break;
    }
  }

  if (Object.hasOwn(exactAliases, requestPath)) return exactAliases[requestPath];

  for (const [fromPrefix, toPrefix] of prefixAliases) {
    if (requestPath.startsWith(fromPrefix)) {
      return `${toPrefix}${requestPath.slice(fromPrefix.length)}`;
    }
  }

  return requestPath;
}

function isInsideDocsRoot(absolutePath) {
  const relative = path.relative(docsRoot, absolutePath);
  return relative === "" || (!relative.startsWith("..") && !path.isAbsolute(relative));
}

function absoluteCandidate(candidatePath) {
  const normalized = path.normalize(candidatePath);
  const safePath = normalized.replace(/^[/\\]+/, "").replace(/^(\.\.(\/|\\|$))+/, "");
  const absolutePath = path.join(docsRoot, safePath);
  if (!isInsideDocsRoot(absolutePath)) return null;
  return absolutePath;
}

function markdownAliasCandidates(requestPath) {
  if (!markdownAliasPrefix) return [];
  const trimmed = requestPath.replace(/\/+$/, "").replace(/^\/+/, "");
  if (!trimmed) return [];

  if (path.extname(trimmed) === ".md") {
    return [`${markdownAliasPrefix}/${trimmed}`];
  }
  if (!path.extname(trimmed)) {
    return [`${markdownAliasPrefix}/${trimmed}.md`];
  }
  return [];
}

function resolveCandidate(candidatePath) {
  const absolutePath = absoluteCandidate(candidatePath === "/" ? indexPath : candidatePath);
  if (!absolutePath) return null;

  if (existsSync(absolutePath)) {
    const stat = statSync(absolutePath);
    if (stat.isDirectory()) {
      const directoryIndexPath = path.join(absolutePath, "index.html");
      if (existsSync(directoryIndexPath)) return directoryIndexPath;
    } else {
      return absolutePath;
    }
  }

  if (!path.extname(absolutePath)) {
    const markdownPath = `${absolutePath}.md`;
    if (existsSync(markdownPath)) return markdownPath;
  }

  const directoryIndexPath = path.join(absolutePath, "index.html");
  if (existsSync(directoryIndexPath)) return directoryIndexPath;
  return null;
}

function resolveRequestPath(requestPath) {
  let aliasedPath;
  try {
    aliasedPath = decodeURIComponent(aliasRequestPath(requestPath));
  } catch {
    return null;
  }

  for (const candidate of [
    aliasedPath,
    ...markdownAliasCandidates(requestPath),
    ...markdownAliasCandidates(aliasedPath),
  ]) {
    const resolved = resolveCandidate(candidate);
    if (resolved) return resolved;
  }
  return null;
}

function sendJson(response, statusCode, value) {
  response.writeHead(statusCode, { "content-type": "application/json; charset=utf-8" });
  response.end(`${JSON.stringify(value)}\n`);
}

function manifest() {
  try {
    return JSON.parse(readFileSync(path.join(docsRoot, "manifest.json"), "utf8"));
  } catch {
    return {};
  }
}

function docsSha() {
  const data = manifest();
  return data.sha ?? data.sourceDigest ?? null;
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
  const url = new URL(request.url ?? "/", baseUrl);

  if (url.pathname === "/health") {
    const healthFile = absoluteCandidate(healthPath);
    const manifestPath = path.join(docsRoot, "manifest.json");
    const ok = Boolean(healthFile && existsSync(healthFile));
    sendJson(response, ok ? 200 : 503, {
      ok,
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
  if (new URL(request.url ?? "/", baseUrl).pathname === "/health") {
    serveDocs(request, response);
    return;
  }
  const host = (request.headers.host ?? new URL(baseUrl).host).replace(/:80$/, "");
  response.writeHead(308, { location: `https://${host}${request.url ?? "/"}` });
  response.end();
});

const httpsServer = createHttpsServer(
  { cert: readFileSync(tlsCertFile), key: readFileSync(tlsKeyFile) },
  serveDocs,
);

httpServer.listen(port, (error) => {
  if (error) {
    console.error(`Failed to start ${siteName} HTTP server:`, error);
    process.exit(1);
  }
  console.log(`${siteName} HTTP server serving ${docsRoot} on port ${port}`);
});

httpsServer.listen(httpsPort, (error) => {
  if (error) {
    console.error(`Failed to start ${siteName} HTTPS server:`, error);
    process.exit(1);
  }
  console.log(`${siteName} HTTPS server serving ${docsRoot} on port ${httpsPort}`);
});
