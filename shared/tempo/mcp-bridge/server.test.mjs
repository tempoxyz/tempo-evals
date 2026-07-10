import assert from "node:assert/strict";
import test from "node:test";

process.env.NODE_ENV = "test";
process.env.MCP_TOOL_MODE = "direct";
process.env.MCP_UPSTREAM_URL = "https://example.test/mcp";
process.env.MCP_TRACE_PATH = "/tmp/tempo-mcp-bridge-test.trace.jsonl";
const { allowedToolNames, filterTools, isAllowedToolCall, parseMcpPayload } = await import("./server.mjs");

test("direct mode exposes data tools and direct docs retrieval", () => {
  assert.deepEqual(allowedToolNames("direct").slice(-3), ["docs_search", "docs_find_pages", "docs_read_page"]);
  assert.deepEqual(
    filterTools({ result: { tools: [{ name: "v1_blocks_get" }, { name: "docs_search" }, { name: "docs_code" }] } }, "direct").result.tools,
    [{ name: "v1_blocks_get" }, { name: "docs_search" }],
  );
});

test("code mode keeps data tools and exposes only docs code mode", () => {
  assert.equal(allowedToolNames("code").includes("v1_blocks_get"), true);
  assert.equal(allowedToolNames("code").includes("docs_code"), true);
  assert.deepEqual(
    filterTools({ result: { tools: [{ name: "v1_blocks_get" }, { name: "docs_search" }, { name: "docs_code" }] } }, "code").result.tools,
    [{ name: "v1_blocks_get" }, { name: "docs_code" }],
  );
});

test("parses a Streamable HTTP SSE tools/list response", () => {
  const payload = { jsonrpc: "2.0", id: 1, result: { tools: [{ name: "code" }] } };
  assert.deepEqual(
    parseMcpPayload(`event: message\ndata: ${JSON.stringify(payload)}\n\n`, "text/event-stream"),
    payload,
  );
});

test("direct and code modes reject each other's tool calls", () => {
  const call = (name) => ({ method: "tools/call", params: { name } });
  assert.equal(isAllowedToolCall(call("v1_blocks_get"), "direct"), true);
  assert.equal(isAllowedToolCall(call("v1_blocks_get"), "code"), true);
  assert.equal(isAllowedToolCall(call("docs_code"), "direct"), false);
  assert.equal(isAllowedToolCall(call("docs_code"), "code"), true);
  assert.equal(isAllowedToolCall(call("docs_read_page"), "code"), false);
});
