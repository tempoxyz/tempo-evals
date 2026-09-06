import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { createServer, type IncomingHttpHeaders, type IncomingMessage, type ServerResponse } from "node:http";
import { dirname } from "node:path";

type ToolMode = "direct" | "code";
type Payload = Record<string, any>;

const mode = process.env.MCP_TOOL_MODE;
const upstream = process.env.MCP_UPSTREAM_URL;
const apiKey = process.env.MCP_API_KEY;
const port = Number(process.env.PORT ?? "8787");
const tracePath = process.env.MCP_TRACE_PATH ?? "/var/log/tempo-mcp/trace.jsonl";
const targetId = process.env.MCP_TARGET_ID ?? "tempo-api-mcp-v1";
const MCP_HEADER_NAMES = ["mcp-session-id", "mcp-protocol-version", "last-event-id"];
const DATA_TOOLS = [
  "v1_addresses_address_activities",
  "v1_addresses_address_balances",
  "v1_blocks_block",
  "v1_blocks_get",
  "v1_exchange_pairs_base_get",
  "v1_exchange_swaps",
  "v1_fee-amm_mints",
  "v1_fee-amm_pools",
  "v1_tokens_get",
  "v1_tokens_token_holders",
  "v1_tokens_token_transactions",
  "v1_transactions_get",
  "v1_transactions_transactionHash_activities",
  "v1_transactions_transactionHash_get",
  "v1_transfers",
];
const DOCS_TOOLS: Record<ToolMode, string[]> = {
  direct: ["docs_search", "docs_find_pages", "docs_read_page"],
  code: ["docs_code"],
};
const GATEWAY_TOOLS = new Set(["search_tools", "get_tool_details", "call_read_tool", "call_write_tool"]);
const INVOCATION_TOOLS = new Set(["call_read_tool", "call_write_tool"]);

function isToolMode(value: unknown): value is ToolMode {
  return value === "direct" || value === "code";
}

if (!isToolMode(mode) || !upstream) {
  throw new Error("MCP_TOOL_MODE must be direct or code and MCP_UPSTREAM_URL is required");
}
const toolMode: ToolMode = mode;
const upstreamUrl = upstream;
mkdirSync(dirname(tracePath), { recursive: true });
appendFileSync(tracePath, "");

export function allowedToolNames(toolMode: ToolMode): string[] {
  return [...DATA_TOOLS, ...DOCS_TOOLS[toolMode]];
}

export function isJsonRpcObject(value: unknown): value is Payload {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function isAllowedToolCall(payload: unknown, toolMode: ToolMode): boolean {
  if (!isJsonRpcObject(payload)) return false;
  if (payload.method !== "tools/call") return true;
  const gatewayTool = payload.params?.name;
  if (gatewayTool === "search_tools") return true;
  if (!GATEWAY_TOOLS.has(gatewayTool)) return false;
  const logicalTool = payload.params?.arguments?.name;
  if (!allowedToolNames(toolMode).includes(logicalTool)) return false;
  if (gatewayTool === "call_read_tool") {
    return DATA_TOOLS.includes(logicalTool) || DOCS_TOOLS.direct.includes(logicalTool);
  }
  if (gatewayTool === "call_write_tool") {
    return DOCS_TOOLS.code.includes(logicalTool);
  }
  return true;
}

function mcpResponseHeaders(headers?: Headers): Record<string, string> {
  return Object.fromEntries(
    MCP_HEADER_NAMES.flatMap((name) => {
      const value = headers?.get(name);
      return value ? [[name, value]] : [];
    }),
  );
}

function reply(response: ServerResponse, payload: unknown, status = 200, upstreamHeaders?: Headers): void {
  response.writeHead(status, { "content-type": "application/json", ...mcpResponseHeaders(upstreamHeaders) });
  response.end(`${JSON.stringify(payload)}\n`);
}

function denied(id: unknown, name: unknown): Payload {
  const error = typeof name === "string"
    ? { code: -32601, message: `Tool unavailable in ${mode} mode: ${name}` }
    : { code: -32602, message: "Tool name must be a string" };
  return { jsonrpc: "2.0", id, error };
}

function trace(event: Payload): void {
  mkdirSync(dirname(tracePath), { recursive: true });
  appendFileSync(tracePath, `${JSON.stringify({ at: new Date().toISOString(), mode, target_id: targetId, ...event })}\n`);
}

export function upstreamHeaders(requestHeaders: IncomingHttpHeaders): Record<string, string> {
  const contentType = requestHeaders["content-type"];
  const accept = requestHeaders.accept;
  const headers: Record<string, string> = {
    "content-type": typeof contentType === "string" ? contentType : "application/json",
    accept: typeof accept === "string" ? accept : "application/json",
  };
  if (apiKey) headers.authorization = `Bearer ${apiKey}`;
  for (const name of MCP_HEADER_NAMES) {
    const value = requestHeaders[name];
    if (typeof value === "string") headers[name] = value;
  }
  return headers;
}

async function proxy(request: IncomingMessage, body: Payload): Promise<{ status: number; headers: Headers; text: string }> {
  const response = await fetch(upstreamUrl, {
    method: request.method,
    headers: upstreamHeaders(request.headers),
    body: request.method === "GET" ? undefined : JSON.stringify(body),
  });
  return { status: response.status, headers: response.headers, text: await response.text() };
}

export function filterGatewayTools(payload: Payload): Payload {
  if (!payload?.result?.tools) return payload;
  return { ...payload, result: { ...payload.result, tools: payload.result.tools.filter((tool: Payload) => GATEWAY_TOOLS.has(tool.name)) } };
}

export function parseMcpPayload(text: string, contentType = ""): Payload {
  if (!contentType.includes("text/event-stream")) return JSON.parse(text) as Payload;
  const data = text
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).trim())
    .filter(Boolean)
    .at(-1);
  if (!data) throw new Error("MCP SSE response did not include data");
  return JSON.parse(data) as Payload;
}

export function toolCallSucceeded(text: string, contentType: string, status: number): boolean {
  if (status < 200 || status >= 300) return false;
  try {
    const payload = parseMcpPayload(text, contentType);
    return !payload.error && payload.result?.isError !== true;
  } catch {
    return false;
  }
}

function filterCatalog(catalog: Payload, toolMode: ToolMode): Payload {
  if (!catalog?.tools) return catalog;
  const names = new Set(allowedToolNames(toolMode));
  return { ...catalog, tools: catalog.tools.filter((tool: Payload) => names.has(tool.name)) };
}

export function filterSearchResult(payload: Payload, toolMode: ToolMode): Payload {
  if (!payload?.result) return payload;
  const result = { ...payload.result };
  if (result.structuredContent) result.structuredContent = filterCatalog(result.structuredContent, toolMode);
  if (Array.isArray(result.content)) {
    result.content = result.content.map((item: Payload) => {
      if (item?.type !== "text") return item;
      try {
        return { ...item, text: JSON.stringify(filterCatalog(JSON.parse(item.text), toolMode)) };
      } catch {
        return item;
      }
    });
  }
  return { ...payload, result };
}

export function traceToolCall(payload: Payload): Payload {
  const gatewayTool = payload?.params?.name;
  const gatewayArguments = payload?.params?.arguments ?? {};
  if (!INVOCATION_TOOLS.has(gatewayTool)) return { tool: gatewayTool, arguments: gatewayArguments };
  return { tool: gatewayArguments.name, arguments: gatewayArguments.arguments ?? {}, gateway_tool: gatewayTool };
}

function requestedTool(payload: Payload): unknown {
  const gatewayTool = payload?.params?.name;
  if (gatewayTool === "get_tool_details" || (typeof gatewayTool === "string" && gatewayTool.startsWith("call_"))) {
    return payload?.params?.arguments?.name ?? gatewayTool;
  }
  return gatewayTool;
}

export function responseDigest(text: string): string {
  return createHash("sha256").update(text).digest("hex");
}

export async function handleRequest(request: IncomingMessage, response: ServerResponse): Promise<void> {
  if (request.url === "/health") return reply(response, { ok: true, mode, tools: allowedToolNames(toolMode) });
  if (request.url === "/trace") {
    const events = readFileSync(tracePath, "utf8").split("\n").filter(Boolean).map((line) => JSON.parse(line));
    return reply(response, { events });
  }
  if (request.url !== "/mcp") return reply(response, { error: "Not found" }, 404);
  const raw = await new Promise<string>((resolve, reject) => {
    let value = "";
    request.on("data", (chunk) => { value += String(chunk); });
    request.on("end", () => resolve(value));
    request.on("error", reject);
  });
  let body: Payload;
  try {
    body = raw ? JSON.parse(raw) as Payload : {};
  } catch {
    return reply(response, { error: "Invalid JSON" }, 400);
  }
  if (!isJsonRpcObject(body)) return reply(response, { error: "JSON-RPC batches are unsupported" }, 400);
  const tool = requestedTool(body);
  if (!isAllowedToolCall(body, toolMode)) {
    trace({ method: body.method, tool, allowed: false });
    return reply(response, denied(body.id, tool));
  }
  const started = performance.now();
  try {
    const upstreamResponse = await proxy(request, body);
    const call = body.method === "tools/call" ? traceToolCall(body) : {};
    const contentType = upstreamResponse.headers.get("content-type") ?? "";
    trace({
      method: body.method,
      ...call,
      allowed: true,
      ...(body.method === "tools/call" ? { succeeded: toolCallSucceeded(upstreamResponse.text, contentType, upstreamResponse.status) } : {}),
      response_sha256: responseDigest(upstreamResponse.text),
      duration_ms: Math.round(performance.now() - started),
    });
    if (body.method === "tools/list" || body.params?.name === "search_tools") {
      const parsed = parseMcpPayload(upstreamResponse.text, contentType);
      return reply(response, body.method === "tools/list" ? filterGatewayTools(parsed) : filterSearchResult(parsed, toolMode), upstreamResponse.status, upstreamResponse.headers);
    }
    response.writeHead(upstreamResponse.status, {
      "content-type": upstreamResponse.headers.get("content-type") ?? "application/json",
      ...mcpResponseHeaders(upstreamResponse.headers),
    });
    response.end(upstreamResponse.text);
  } catch (error) {
    trace({
      method: body.method,
      tool,
      allowed: true,
      ...(body.method === "tools/call" ? { succeeded: false } : {}),
      error: error instanceof Error ? error.message : String(error),
    });
    reply(response, { jsonrpc: "2.0", id: body.id ?? null, error: { code: -32603, message: "MCP bridge upstream request failed" } }, 502);
  }
}

if (process.env.NODE_ENV !== "test") createServer(handleRequest).listen(port);
