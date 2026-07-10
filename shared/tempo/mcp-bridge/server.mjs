import { createServer } from "node:http";
import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

const mode = process.env.MCP_TOOL_MODE;
const upstream = process.env.MCP_UPSTREAM_URL;
const port = Number(process.env.PORT ?? "8787");
const tracePath = process.env.MCP_TRACE_PATH ?? "/var/log/tempo-mcp/trace.jsonl";
const targetId = process.env.MCP_TARGET_ID ?? "tempo-mcp-codemode-v1";
const MCP_HEADER_NAMES = [
  "mcp-session-id",
  "mcp-protocol-version",
  "last-event-id",
];
const allowed = {
  direct: new Set(["search", "find_pages", "read_page"]),
  code: new Set(["code"]),
}[mode];

if (!allowed || !upstream) throw new Error("MCP_TOOL_MODE and MCP_UPSTREAM_URL are required");
mkdirSync(dirname(tracePath), { recursive: true });
appendFileSync(tracePath, "");

export function allowedToolNames(toolMode) {
  const tools = { direct: ["search", "find_pages", "read_page"], code: ["code"] };
  if (!(toolMode in tools)) throw new Error(`Unknown MCP tool mode: ${toolMode}`);
  return tools[toolMode];
}

export function isAllowedToolCall(payload, toolMode) {
  if (payload?.method !== "tools/call") return true;
  return allowedToolNames(toolMode).includes(payload?.params?.name);
}

function mcpResponseHeaders(headers) {
  return Object.fromEntries(
    MCP_HEADER_NAMES.flatMap((name) => {
      const value = headers?.get(name);
      return value ? [[name, value]] : [];
    }),
  );
}

function reply(response, payload, status = 200, upstreamHeaders) {
  response.writeHead(status, {
    "content-type": "application/json",
    ...mcpResponseHeaders(upstreamHeaders),
  });
  response.end(`${JSON.stringify(payload)}\n`);
}

function denied(id, name) {
  return { jsonrpc: "2.0", id, error: { code: -32601, message: `Tool unavailable in ${mode} mode: ${name}` } };
}

function trace(event) {
  mkdirSync(dirname(tracePath), { recursive: true });
  appendFileSync(tracePath, `${JSON.stringify({ at: new Date().toISOString(), mode, target_id: targetId, ...event })}\n`);
}

async function proxy(request, body) {
  const headers = {
    "content-type": request.headers["content-type"] ?? "application/json",
    accept: request.headers.accept ?? "application/json",
  };
  for (const name of MCP_HEADER_NAMES) {
    const value = request.headers[name];
    if (typeof value === "string") headers[name] = value;
  }
  const response = await fetch(upstream, {
    method: request.method,
    headers,
    body: request.method === "GET" ? undefined : JSON.stringify(body),
  });
  return { status: response.status, headers: response.headers, text: await response.text() };
}

export function filterTools(payload, toolMode) {
  if (!payload?.result?.tools) return payload;
  const names = new Set(allowedToolNames(toolMode));
  return { ...payload, result: { ...payload.result, tools: payload.result.tools.filter((tool) => names.has(tool.name)) } };
}

export function parseMcpPayload(text, contentType = "") {
  if (!contentType.includes("text/event-stream")) return JSON.parse(text);
  const data = text
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).trim())
    .find(Boolean);
  if (!data) throw new Error("MCP SSE response did not include data");
  return JSON.parse(data);
}

if (process.env.NODE_ENV !== "test") createServer(async (request, response) => {
  if (request.url === "/health") return reply(response, { ok: true, mode, tools: allowedToolNames(mode) });
  if (request.url !== "/mcp") return reply(response, { error: "Not found" }, 404);
  const raw = await new Promise((resolve, reject) => {
    let value = "";
    request.on("data", (chunk) => { value += chunk; });
    request.on("end", () => resolve(value));
    request.on("error", reject);
  });
  let body;
  try { body = raw ? JSON.parse(raw) : {}; } catch { return reply(response, { error: "Invalid JSON" }, 400); }
  const tool = body?.params?.name;
  if (!isAllowedToolCall(body, mode)) {
    trace({ method: body.method, tool, allowed: false });
    return reply(response, denied(body.id, tool));
  }
  const started = performance.now();
  try {
    const upstreamResponse = await proxy(request, body);
    trace({ method: body?.method, tool, allowed: true, duration_ms: Math.round(performance.now() - started) });
    if (body?.method === "tools/list") {
      const parsed = parseMcpPayload(
        upstreamResponse.text,
        upstreamResponse.headers.get("content-type") ?? "",
      );
      return reply(
        response,
        filterTools(parsed, mode),
        upstreamResponse.status,
        upstreamResponse.headers,
      );
    }
    response.writeHead(upstreamResponse.status, {
      "content-type": upstreamResponse.headers.get("content-type") ?? "application/json",
      ...mcpResponseHeaders(upstreamResponse.headers),
    });
    response.end(upstreamResponse.text);
  } catch (error) {
    trace({ method: body?.method, tool, allowed: true, error: error instanceof Error ? error.message : String(error) });
    reply(response, { jsonrpc: "2.0", id: body?.id ?? null, error: { code: -32603, message: "MCP bridge upstream request failed" } }, 502);
  }
}).listen(port);
