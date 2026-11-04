// Trusted Compose sidecar. Account credentials and authenticated upstream CDP
// URLs never enter the agent or the Playwright MCP process (which runs code).
import http from "node:http";
import https from "node:https";
import { pathToFileURL } from "node:url";

type Session = { endpoint: string; release: () => Promise<void> };
type Request = typeof fetch;
const lifetimeSeconds = 2400; // Bounds leaks even if Compose cannot stop cleanly.

export async function createSession(
  profile: string,
  env: NodeJS.ProcessEnv = process.env,
  request: Request = fetch,
): Promise<Session> {
  async function api(url: string, method: string, headers: Record<string, string>, body?: object) {
    const response = await request(url, {
      method, headers: { ...headers, "Content-Type": "application/json" },
      body: body && JSON.stringify(body), signal: AbortSignal.timeout(30_000),
    });
    // Provider error bodies can contain authenticated URLs. Do not log them.
    if (!response.ok) throw new Error(`${profile} session ${method} failed: HTTP ${response.status}`);
    return response;
  }
  if (profile === "browserbase") {
    const headers = { "x-bb-api-key": env.BROWSERBASE_API_KEY! };
    const base = "https://api.browserbase.com/v1/sessions";
    const session = await (await api(base, "POST", headers, {
      projectId: env.BROWSERBASE_PROJECT_ID, timeout: lifetimeSeconds,
      keepAlive: true, proxies: false,
      browserSettings: { solveCaptchas: false, advancedStealth: false, blockAds: false },
    })).json();
    const release = async () => { await api(`${base}/${encodeURIComponent(session.id)}`, "POST", headers, { status: "REQUEST_RELEASE" }); };
    if (!session.id || !session.connectUrl) {
      if (session.id) await release();
      throw new Error("browserbase returned no session ID or CDP endpoint");
    }
    return { endpoint: session.connectUrl, release };
  }
  if (profile === "kernel") {
    const headers = { Authorization: `Bearer ${env.KERNEL_API_KEY}` };
    const base = "https://api.onkernel.com/browsers";
    const session = await (await api(base, "POST", headers, {
      headless: true, stealth: false, timeout_seconds: lifetimeSeconds,
    })).json();
    const release = async () => { await api(`${base}/${encodeURIComponent(session.session_id)}`, "DELETE", headers); };
    if (!session.session_id || !session.cdp_ws_url) {
      if (session.session_id) await release();
      throw new Error("kernel returned no session ID or CDP endpoint");
    }
    return { endpoint: session.cdp_ws_url, release };
  }
  throw new Error("Unsupported cloud browser profile");
}

// Raw WebSocket upgrade relay: only the trial's CDP capability is exposed.
// No provider REST proxy, account key, upstream headers, or endpoint is returned.
export function cdpRelay(endpoint: string) {
  const upstream = new URL(endpoint);
  if (!["ws:", "wss:"].includes(upstream.protocol)) throw new Error("Invalid CDP protocol");
  const server = http.createServer((req, res) => {
    res.writeHead(req.url === "/health" ? 200 : 404).end();
  });
  server.on("upgrade", (req, socket, head) => {
    const dial = upstream.protocol === "wss:" ? https.request : http.request;
    const proxy = dial(new URL(endpoint.replace(/^ws/, "http")), {
      headers: {
        Host: upstream.host, Upgrade: "websocket", Connection: "Upgrade",
        "Sec-WebSocket-Key": req.headers["sec-websocket-key"]!,
        "Sec-WebSocket-Version": "13",
      },
    });
    proxy.setTimeout(30_000, () => proxy.destroy());
    proxy.on("upgrade", (res, remote, remoteHead) => {
      proxy.setTimeout(0);
      socket.write("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n" +
        `Sec-WebSocket-Accept: ${res.headers["sec-websocket-accept"]}\r\n\r\n`);
      if (head.length) remote.write(head);
      if (remoteHead.length) socket.write(remoteHead);
      socket.pipe(remote).pipe(socket);
      socket.on("close", () => remote.destroy());
      remote.on("close", () => socket.destroy());
      remote.on("error", () => socket.destroy());
    });
    proxy.on("response", (res) => {
      console.error(`Cloud browser CDP connection rejected: HTTP ${res.statusCode}`);
      res.resume(); socket.end("HTTP/1.1 502 Bad Gateway\r\nConnection: close\r\n\r\n");
    });
    proxy.on("error", () => socket.destroy());
    socket.on("error", () => proxy.destroy());
    proxy.end();
  });
  return server;
}

async function main() {
  let stopping = false;
  let session: Session | undefined;
  const stop = async () => {
    if (stopping) return;
    stopping = true;
    try { await session?.release(); }
    catch { console.error("Cloud browser release failed; provider timeout remains active"); }
    process.exit(0);
  };
  // Register before creation, so cancellation during the API request still releases.
  for (const signal of ["SIGTERM", "SIGINT"] as const) process.on(signal, () => {
    if (session) void stop();
    else stopping = true;
  });
  session = await createSession(process.env.CHECKOUT_BROWSER_PROFILE!);
  if (stopping) { stopping = false; await stop(); return; }
  try {
    const relay = cdpRelay(session.endpoint);
    relay.on("error", () => void stop());
    relay.listen(9222, "0.0.0.0");
    setTimeout(() => void stop(), lifetimeSeconds * 1000);
  } catch { await stop(); }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(() => { console.error("Cloud browser session setup failed"); process.exit(1); });
}
