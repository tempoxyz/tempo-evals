import { createServer } from "node:http";
import { createHash } from "node:crypto";
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { dirname } from "node:path";

const mode = process.env.MCP_TOOL_MODE;
const upstream = process.env.MCP_UPSTREAM_URL;
const port = Number(process.env.PORT ?? "8787");
const tracePath = process.env.MCP_TRACE_PATH ?? "/var/log/tempo-mcp/trace.jsonl";
const targetId = process.env.MCP_TARGET_ID ?? "tempo-api-mcp-v1";
const MCP_HEADER_NAMES = [
  "mcp-session-id",
  "mcp-protocol-version",
  "last-event-id",
];
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
const DOCS_TOOLS = {
  direct: ["docs_search", "docs_find_pages", "docs_read_page"],
  code: ["docs_code"],
};
const GATEWAY_TOOLS = new Set([
  "search_tools",
  "get_tool_details",
  "call_read_tool",
  "call_write_tool",
]);

if (!(mode in DOCS_TOOLS) || !upstream) {
  throw new Error("MCP_TOOL_MODE must be direct or code and MCP_UPSTREAM_URL is required");
}
mkdirSync(dirname(tracePath), { recursive: true });
appendFileSync(tracePath, "");

export function allowedToolNames(toolMode) {
  if (!(toolMode in DOCS_TOOLS)) throw new Error(`Unknown MCP tool mode: ${toolMode}`);
  return [...DATA_TOOLS, ...DOCS_TOOLS[toolMode]];
}

export function isJsonRpcObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function isAllowedToolCall(payload, toolMode) {
  if (!isJsonRpcObject(payload)) return false;
  if (payload?.method !== "tools/call") return true;
  const gatewayTool = payload?.params?.name;
  if (gatewayTool === "search_tools") return true;
  if (!GATEWAY_TOOLS.has(gatewayTool)) return false;
  const logicalTool = payload?.params?.arguments?.name;
  if (!allowedToolNames(toolMode).includes(logicalTool)) return false;
  if (gatewayTool === "call_read_tool") return DATA_TOOLS.includes(logicalTool);
  if (gatewayTool === "call_write_tool") return DOCS_TOOLS[toolMode].includes(logicalTool);
  return true;
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
  const error = typeof name === "string"
    ? { code: -32601, message: `Tool unavailable in ${mode} mode: ${name}` }
    : { code: -32602, message: "Tool name must be a string" };
  return { jsonrpc: "2.0", id, error };
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

export function filterGatewayTools(payload) {
  if (!payload?.result?.tools) return payload;
  return {
    ...payload,
    result: {
      ...payload.result,
      tools: payload.result.tools.filter((tool) => GATEWAY_TOOLS.has(tool.name)),
    },
  };
}

export function parseMcpPayload(text, contentType = "") {
  if (!contentType.includes("text/event-stream")) return JSON.parse(text);
  const data = text
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).trim())
    .filter(Boolean)
    .at(-1);
  if (!data) throw new Error("MCP SSE response did not include data");
  return JSON.parse(data);
}

export function toolCallSucceeded(text, contentType, status) {
  if (status < 200 || status >= 300) return false;
  try {
    const payload = parseMcpPayload(text, contentType);
    return !payload?.error && payload?.result?.isError !== true;
  } catch {
    return false;
  }
}

function filterCatalog(catalog, toolMode) {
  if (!catalog?.tools) return catalog;
  const names = new Set(allowedToolNames(toolMode));
  return { ...catalog, tools: catalog.tools.filter((tool) => names.has(tool.name)) };
}

export function filterSearchResult(payload, toolMode) {
  if (!payload?.result) return payload;
  const result = { ...payload.result };
  if (result.structuredContent) {
    result.structuredContent = filterCatalog(result.structuredContent, toolMode);
  }
  if (Array.isArray(result.content)) {
    result.content = result.content.map((item) => {
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

export function traceToolCall(payload) {
  const gatewayTool = payload?.params?.name;
  const gatewayArguments = payload?.params?.arguments ?? {};
  if (!new Set(["call_read_tool", "call_write_tool"]).has(gatewayTool)) {
    return { tool: gatewayTool, arguments: gatewayArguments };
  }
  return {
    tool: gatewayArguments.name,
    arguments: gatewayArguments.arguments ?? {},
    gateway_tool: gatewayTool,
  };
}

function requestedTool(payload) {
  const gatewayTool = payload?.params?.name;
  if (
    gatewayTool === "get_tool_details"
    || (typeof gatewayTool === "string" && gatewayTool.startsWith("call_"))
  ) {
    return payload?.params?.arguments?.name ?? gatewayTool;
  }
  return gatewayTool;
}

export function responseDigest(text) {
  return createHash("sha256").update(text).digest("hex");
}

export async function handleRequest(request, response) {
  if (request.url === "/health") return reply(response, { ok: true, mode, tools: allowedToolNames(mode) });
  if (request.url === "/trace") {
    const events = readFileSync(tracePath, "utf8")
      .split("\n")
      .filter(Boolean)
      .map((line) => JSON.parse(line));
    return reply(response, { events });
  }
  if (request.url !== "/mcp") return reply(response, { error: "Not found" }, 404);
  const raw = await new Promise((resolve, reject) => {
    let value = "";
    request.on("data", (chunk) => { value += chunk; });
    request.on("end", () => resolve(value));
    request.on("error", reject);
  });
  let body;
  try { body = raw ? JSON.parse(raw) : {}; } catch { return reply(response, { error: "Invalid JSON" }, 400); }
  if (!isJsonRpcObject(body)) return reply(response, { error: "JSON-RPC batches are unsupported" }, 400);
  const tool = requestedTool(body);
  if (!isAllowedToolCall(body, mode)) {
    trace({ method: body.method, tool, allowed: false });
    return reply(response, denied(body.id, tool));
  }
  const started = performance.now();
  try {
    const upstreamResponse = await proxy(request, body);
    const call = body?.method === "tools/call" ? traceToolCall(body) : {};
    const contentType = upstreamResponse.headers.get("content-type") ?? "";
    trace({
      method: body?.method,
      ...call,
      allowed: true,
      ...(body?.method === "tools/call"
        ? { succeeded: toolCallSucceeded(upstreamResponse.text, contentType, upstreamResponse.status) }
        : {}),
      response_sha256: responseDigest(upstreamResponse.text),
      duration_ms: Math.round(performance.now() - started),
    });
    if (body?.method === "tools/list" || body?.params?.name === "search_tools") {
      const parsed = parseMcpPayload(
        upstreamResponse.text,
        contentType,
      );
      return reply(
        response,
        body?.method === "tools/list" ? filterGatewayTools(parsed) : filterSearchResult(parsed, mode),
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
    trace({
      method: body?.method,
      tool,
      allowed: true,
      ...(body?.method === "tools/call" ? { succeeded: false } : {}),
      error: error instanceof Error ? error.message : String(error),
    });
    reply(response, { jsonrpc: "2.0", id: body?.id ?? null, error: { code: -32603, message: "MCP bridge upstream request failed" } }, 502);
  }
}

if (process.env.NODE_ENV !== "test") createServer(handleRequest).listen(port);
