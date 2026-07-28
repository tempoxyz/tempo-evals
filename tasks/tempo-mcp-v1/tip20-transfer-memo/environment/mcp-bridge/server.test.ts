import assert from "node:assert/strict";
import { createServer } from "node:http";
import test from "node:test";

process.env.NODE_ENV = "test";
process.env.MCP_TOOL_MODE = "direct";
process.env.MCP_UPSTREAM_URL = "https://example.test/mcp";
process.env.MCP_API_KEY = "test-api-key";
process.env.MCP_TRACE_PATH = "/tmp/tempo-mcp-bridge-test.trace.jsonl";
const {
  allowedToolNames,
  filterGatewayTools,
  filterSearchResult,
  handleRequest,
  isAllowedToolCall,
  isJsonRpcObject,
  parseMcpPayload,
  responseDigest,
  toolCallSucceeded,
  traceToolCall,
  upstreamHeaders,
} = await import("./server.ts");

test("sends the configured Tempo key as a Bearer credential", () => {
  assert.equal(upstreamHeaders({}).authorization, "Bearer test-api-key");
});

test("rejects non-string tool names without crashing", async () => {
  const server = createServer(handleRequest);
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("Expected a TCP listener");
  try {
    const response = await fetch(`http://127.0.0.1:${address.port}/mcp`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/call", params: { name: {} } }),
    });
    assert.deepEqual(await response.json(), { jsonrpc: "2.0", id: 1, error: { code: -32602, message: "Tool name must be a string" } });
    assert.equal((await fetch(`http://127.0.0.1:${address.port}/health`)).status, 200);
  } finally {
    await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
  }
});

test("tools/list exposes only the progressive gateway", () => {
  assert.deepEqual(allowedToolNames("direct").slice(-3), ["docs_search", "docs_find_pages", "docs_read_page"]);
  assert.deepEqual(
    filterGatewayTools({ result: { tools: [{ name: "search_tools" }, { name: "get_tool_details" }, { name: "call_read_tool" }, { name: "call_write_tool" }, { name: "ignored" }] } }).result.tools,
    [{ name: "search_tools" }, { name: "get_tool_details" }, { name: "call_read_tool" }, { name: "call_write_tool" }],
  );
});

test("code mode keeps data tools and exposes only docs code mode", () => {
  assert.equal(allowedToolNames("code").includes("v1_blocks_get"), true);
  assert.equal(allowedToolNames("code").includes("docs_code"), true);
});

test("parses a Streamable HTTP SSE tools/list response", () => {
  const payload = { jsonrpc: "2.0", id: 1, result: { tools: [{ name: "code" }] } };
  assert.deepEqual(parseMcpPayload(`event: message\ndata: ${JSON.stringify(payload)}\n\n`, "text/event-stream"), payload);
});

test("credits only successful MCP tool responses", () => {
  assert.equal(toolCallSucceeded('{"jsonrpc":"2.0","result":{"content":[]}}', "application/json", 200), true);
  assert.equal(toolCallSucceeded('{"jsonrpc":"2.0","result":{"isError":true}}', "application/json", 200), false);
  assert.equal(toolCallSucceeded('{"jsonrpc":"2.0","error":{"code":-1}}', "application/json", 200), false);
  assert.equal(toolCallSucceeded("not JSON", "application/json", 200), false);
  assert.equal(toolCallSucceeded('{"jsonrpc":"2.0","result":{}}', "application/json", 500), false);
});

test("hashes MCP responses for evidence provenance", () => {
  assert.equal(responseDigest("tempo"), "8d6546721a1d106cf8d27f7326ebae7e83c1592aeb7479b8f7ec9d8d700d464f");
});

test("direct and code modes enforce profile allowlists", () => {
  const call = (gateway: string, name?: string) => ({ method: "tools/call", params: { name: gateway, arguments: name ? { name } : {} } });
  assert.equal(isAllowedToolCall(call("search_tools"), "direct"), true);
  assert.equal(isAllowedToolCall(call("call_read_tool", "v1_blocks_get"), "direct"), true);
  assert.equal(isAllowedToolCall(call("call_read_tool", "docs_search"), "direct"), true);
  assert.equal(isAllowedToolCall(call("call_write_tool", "docs_search"), "direct"), false);
  assert.equal(isAllowedToolCall(call("get_tool_details", "docs_code"), "direct"), false);
  assert.equal(isAllowedToolCall(call("call_write_tool", "docs_code"), "code"), true);
  assert.equal(isAllowedToolCall(call("call_read_tool", "docs_read_page"), "code"), false);
  assert.equal(isAllowedToolCall([call("call_write_tool", "docs_code")], "direct"), false);
});

test("rejects JSON-RPC batches at the bridge boundary", () => {
  assert.equal(isJsonRpcObject({ jsonrpc: "2.0", method: "tools/call" }), true);
  assert.equal(isJsonRpcObject([{ jsonrpc: "2.0", method: "tools/call" }]), false);
  assert.equal(isJsonRpcObject(null), false);
});

test("filters progressive search results and traces logical calls", () => {
  const payload = { result: { content: [{ type: "text", text: JSON.stringify({ tools: [{ name: "v1_blocks_get" }, { name: "docs_search" }, { name: "docs_code" }], nextOffset: 10 }) }] } };
  assert.deepEqual(JSON.parse(filterSearchResult(payload, "direct").result.content[0].text), { tools: [{ name: "v1_blocks_get" }, { name: "docs_search" }], nextOffset: 10 });
  assert.deepEqual(traceToolCall({ params: { name: "call_read_tool", arguments: { name: "v1_blocks_get", arguments: { limit: 5 } } } }), { tool: "v1_blocks_get", arguments: { limit: 5 }, gateway_tool: "call_read_tool" });
});
