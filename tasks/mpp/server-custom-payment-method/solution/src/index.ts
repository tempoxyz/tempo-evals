import http from "node:http";
import { writeFileSync } from "node:fs";
import { Method, Receipt, z } from "mppx";
import { Mppx, NodeListener, Request as ServerRequest } from "mppx/server";

const port = Number(process.env.PORT ?? "3000");
const freePath = "/free";
const paidPath = "/paid";
const expectedAccessKey = process.env.MPP_CUSTOM_ACCESS_KEY ?? "stable-bench-access-key";

const benchKey = Method.from({
  name: "bench-key",
  intent: "charge",
  schema: {
    credential: {
      payload: z.object({
        accessKey: z.string(),
      }),
    },
    request: z.object({
      amount: z.string(),
      resource: z.string(),
    }),
  },
});

const benchKeyServer = Method.toServer(benchKey, {
  defaults: {
    amount: "1",
    resource: "paid-json",
  },
  async verify({ credential, request }) {
    if (credential.payload.accessKey !== expectedAccessKey) {
      throw new Error("invalid access key");
    }
    return Receipt.from({
      method: "bench-key",
      status: "success",
      reference: `bench-key:${request.resource}`,
      timestamp: new Date().toISOString(),
    });
  },
});

const mppx = Mppx.create({
  methods: [benchKeyServer],
  secretKey: process.env.MPP_SECRET_KEY ?? "stable-bench-mpp-secret-key-000000001",
});

function writeJson(response: http.ServerResponse, status: number, body: unknown) {
  response.writeHead(status, { "content-type": "application/json" });
  response.end(JSON.stringify(body));
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);

  if (request.method === "GET" && url.pathname === freePath) {
    writeJson(response, 200, { ok: true, endpoint: "free" });
    return;
  }

  if (request.method === "GET" && url.pathname === paidPath) {
    const result = await mppx.charge({
      amount: "1",
      description: "Paid JSON",
      resource: "paid-json",
    })(ServerRequest.fromNodeListener(request, response));
    if (result.status === 402) return NodeListener.sendResponse(response, result.challenge);
    return NodeListener.sendResponse(
      response,
      result.withReceipt(Response.json({ ok: true, endpoint: "paid" })),
    );
  }

  writeJson(response, 404, { ok: false, error: "not_found" });
});

server.listen(port, "0.0.0.0", () => {
  writeFileSync(
    "out.json",
    `${JSON.stringify({
      freeUrl: `http://127.0.0.1:${port}${freePath}`,
      paidUrl: `http://127.0.0.1:${port}${paidPath}`,
    })}\n`,
  );
});
