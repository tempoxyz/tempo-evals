import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import http from "node:http";
import { once } from "node:events";
import { test } from "node:test";
import { cdpRelay, createSession } from "./session.ts";

for (const profile of ["browserbase", "kernel"]) {
  test(`${profile}: independent sessions and provider-specific release`, async () => {
    const calls: { url: string; init: RequestInit }[] = [];
    let count = 0;
    const request: typeof fetch = async (input, init) => {
      const url = String(input);
      calls.push({ url, init: init! });
      if (url.endsWith("/sessions") || url.endsWith("/browsers")) {
        const id = `trial-${++count}`;
        return Response.json(profile === "kernel"
          ? { session_id: id, cdp_ws_url: `wss://cdp.example/${id}` }
          : { id, connectUrl: `wss://cdp.example/${id}?apiKey=private` });
      }
      return new Response(null, { status: 204 });
    };
    const env = { BROWSERBASE_API_KEY: "bb-private", BROWSERBASE_PROJECT_ID: "project", KERNEL_API_KEY: "kernel-private" };
    const sessions = await Promise.all([createSession(profile, env, request), createSession(profile, env, request)]);
    assert.notEqual(sessions[0].endpoint, sessions[1].endpoint);
    const body = JSON.parse(calls[0].init.body as string);
    if (profile === "kernel") {
      assert.equal(body.stealth, false);
      assert.equal(body.headless, true);
      assert.equal(body.timeout_seconds, 2400);
    } else {
      assert.equal(body.keepAlive, true);
      assert.equal(body.timeout, 2400);
      assert.equal(body.proxies, false);
      assert.equal(body.browserSettings.solveCaptchas, false);
    }
    await Promise.all(sessions.map(s => s.release()));
    assert.equal(calls.length, 4);
    for (const call of calls.slice(2)) {
      assert.match(call.url, /trial-[12]$/);
      assert.equal(call.init.method, profile === "kernel" ? "DELETE" : "POST");
      if (profile === "browserbase") assert.deepEqual(JSON.parse(call.init.body as string), { status: "REQUEST_RELEASE" });
    }
  });
}

test("provider failures omit upstream credential-bearing error bodies", async () => {
  await assert.rejects(createSession("kernel", {}, async () =>
    new Response("secret-key-and-cdp-url", { status: 429 })),
  { message: "kernel session POST failed: HTTP 429" });
});

test("a malformed create response still releases its allocated session", async () => {
  const methods: string[] = [];
  await assert.rejects(createSession("kernel", {}, async (_url, init) => {
    methods.push(init!.method!);
    return methods.length === 1 ? Response.json({ session_id: "allocated" }) : new Response(null, { status: 204 });
  }), /no session ID or CDP endpoint/);
  assert.deepEqual(methods, ["POST", "DELETE"]);
});

test("CDP relay hides the authenticated URL and provider headers", async (t) => {
  const upstream = http.createServer();
  upstream.on("upgrade", (req, socket) => {
    assert.equal(req.url, "/cdp?apiKey=account-secret");
    const accept = createHash("sha1").update(req.headers["sec-websocket-key"] + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest("base64");
    socket.write(`HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ${accept}\r\nX-Account-Secret: hidden\r\n\r\n`);
    const text = Buffer.from("trial-cdp");
    socket.end(Buffer.concat([Buffer.from([0x81, text.length]), text]));
  });
  upstream.listen(0, "127.0.0.1"); await once(upstream, "listening");
  const upstreamPort = (upstream.address() as { port: number }).port;
  const relay = cdpRelay(`ws://127.0.0.1:${upstreamPort}/cdp?apiKey=account-secret`);
  relay.listen(0, "127.0.0.1"); await once(relay, "listening");
  t.after(() => { upstream.close(); relay.close(); });
  const port = (relay.address() as { port: number }).port;
  const health = await fetch(`http://127.0.0.1:${port}/health`);
  assert.equal(health.status, 200); assert.equal(await health.text(), "");
  assert.equal((await fetch(`http://127.0.0.1:${port}/v1/sessions`)).status, 404);
  const request = http.request(`http://127.0.0.1:${port}`, { headers: {
    Connection: "Upgrade", Upgrade: "websocket", "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==", "Sec-WebSocket-Version": "13",
  }});
  const upgraded = once(request, "upgrade"); request.end();
  const [response, socket, head] = await upgraded;
  assert.equal(response.statusCode, 101);
  assert.equal(response.headers["x-account-secret"], undefined);
  const data = head.length ? head : (await once(socket, "data"))[0];
  assert.equal(data.subarray(2).toString(), "trial-cdp");
  socket.destroy();
});
