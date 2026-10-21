// Runs after Link enrollment, before Compose starts the evaluated agent.
import { pathToFileURL } from "node:url";

export async function checkBrowser(endpoint = "http://browser:8931/mcp") {
  let session: string | null = null;
  let id = 0;
  async function rpc(method: string, params: object, notification = false) {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json", Accept: "application/json, text/event-stream",
        "mcp-protocol-version": "2025-03-26",
        ...(session ? { "mcp-session-id": session } : {}),
      },
      body: JSON.stringify({ jsonrpc: "2.0", ...(notification ? {} : { id: ++id }), method, params }),
      signal: AbortSignal.timeout(30_000),
    });
    session = response.headers.get("mcp-session-id") || session;
    if (!response.ok) throw new Error(`Browser readiness ${method}: HTTP ${response.status}`);
    if (notification) { await response.body?.cancel(); return; }
    const body = await response.text();
    const messages = response.headers.get("content-type")?.includes("text/event-stream")
      ? body.split("\n").filter(line => line.startsWith("data:")).map(line => JSON.parse(line.slice(5)))
      : [JSON.parse(body)];
    const message = messages.find(value => value.id === id);
    // Provider error text may contain authenticated URLs; keep diagnostics local.
    if (!message?.result || message.error || message.result.isError) {
      throw new Error(`Browser readiness ${method} failed`);
    }
    return message.result;
  }
  await rpc("initialize", {
    protocolVersion: "2025-03-26", capabilities: {},
    clientInfo: { name: "checkout-browser-readiness", version: "1.0.0" },
  });
  try {
    await rpc("notifications/initialized", {}, true);
    await rpc("tools/call", {
      name: "browser_run_code_unsafe",
      arguments: { code: `async (page) => {
        const response = await page.goto('http://merchant:3000/health', { timeout: 15000 });
        if (response?.status() !== 200 || await response.text() !== 'ok') {
          throw new Error('Merchant unreachable through checkout browser');
        }
      }` },
    });
  } finally {
    try {
      await rpc("tools/call", { name: "browser_close", arguments: {} });
    } finally {
      if (session) await fetch(endpoint, {
        method: "DELETE", headers: { "mcp-session-id": session },
        signal: AbortSignal.timeout(5_000),
      }).catch(() => {});
    }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  checkBrowser().then(() => console.log("Checkout browser ready after Link enrollment")).catch(() => {
    console.error("Checkout browser readiness failed after Link enrollment");
    process.exitCode = 1;
  });
}
