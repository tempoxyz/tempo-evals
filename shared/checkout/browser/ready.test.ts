import assert from "node:assert/strict";
import http from "node:http";
import { once } from "node:events";
import { test } from "node:test";
import { checkBrowser } from "./ready.ts";

for (const broken of [false, true]) {
  test(`readiness ${broken ? "rejects a dead browser behind a healthy MCP server" : "navigates and cleans up"}`, async (t) => {
    const tools: string[] = [];
    let deleted = false;
    const server = http.createServer(async (req, res) => {
      if (req.method === "DELETE") { deleted = true; res.writeHead(200).end(); return; }
      let body = "";
      for await (const chunk of req) body += chunk;
      const message = JSON.parse(body);
      if (message.method === "notifications/initialized") { res.writeHead(202).end(); return; }
      if (message.method !== "initialize") assert.equal(req.headers["mcp-session-id"], "trial-session");
      let result = {};
      if (message.method === "tools/call") {
        tools.push(message.params.name);
        if (message.params.name === "browser_run_code_unsafe") {
          assert.match(message.params.arguments.code, /http:\/\/merchant:3000\/health/);
          result = { isError: broken, content: [{ type: "text", text: broken ? "private upstream error" : "done" }] };
        }
      }
      res.writeHead(200, { "content-type": "text/event-stream", "mcp-session-id": "trial-session" });
      res.end(`event: message\ndata: ${JSON.stringify({ jsonrpc: "2.0", id: message.id, result })}\n\n`);
    });
    server.listen(0, "127.0.0.1"); await once(server, "listening");
    t.after(() => server.close());
    const endpoint = `http://127.0.0.1:${(server.address() as { port: number }).port}/mcp`;
    if (broken) await assert.rejects(checkBrowser(endpoint), { message: "Browser readiness tools/call failed" });
    else await checkBrowser(endpoint);
    assert.deepEqual(tools, ["browser_run_code_unsafe", "browser_close"]);
    assert.equal(deleted, true);
  });
}
