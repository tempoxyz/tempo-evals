import assert from "node:assert/strict";
import test from "node:test";

process.env.NODE_ENV = "test";
process.env.MCP_TOOL_MODE = "direct";
process.env.MCP_UPSTREAM_URL = "https://example.test/mcp";
process.env.MCP_TRACE_PATH = "/tmp/tempo-mcp-bridge-test.trace.jsonl";
const { allowedToolNames, filterTools, isAllowedToolCall, parseMcpPayload } = await import("./server.mjs");

test("direct mode exposes only retrieval tools", () => {
  assert.deepEqual(allowedToolNames("direct"), ["search", "find_pages", "read_page"]);
  assert.deepEqual(
    filterTools({ result: { tools: [{ name: "search" }, { name: "code" }] } }, "direct").result.tools,
    [{ name: "search" }],
  );
});

test("code mode exposes only the code tool", () => {
  assert.deepEqual(allowedToolNames("code"), ["code"]);
  assert.deepEqual(
    filterTools({ result: { tools: [{ name: "search" }, { name: "code" }] } }, "code").result.tools,
    [{ name: "code" }],
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
  assert.equal(isAllowedToolCall(call("search"), "direct"), true);
  assert.equal(isAllowedToolCall(call("code"), "direct"), false);
  assert.equal(isAllowedToolCall(call("code"), "code"), true);
  assert.equal(isAllowedToolCall(call("read_page"), "code"), false);
});
