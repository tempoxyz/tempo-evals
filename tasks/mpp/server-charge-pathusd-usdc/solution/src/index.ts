import http from "node:http";
import { writeFileSync } from "node:fs";
import { Mppx, NodeListener, Request as ServerRequest, tempo } from "mppx/server";
import { tempoRpcClient } from "./tempo-rpc.js";

const port = Number(process.env.PORT ?? "3000");
const freePath = "/free";
const paidPath = "/paid";
const pathUsd = "0x20c0000000000000000000000000000000000000";
const recipient = (process.env.RECIPIENT_ADDRESS ?? "0x1111111111111111111111111111111111111111") as `0x${string}`;
const chargeAmount = process.env.MPP_CHARGE_AMOUNT ?? "0.01";
const usdc = "0x20C000000000000000000000b9537d11c60E8b50";

const mppx = Mppx.create({
  methods: [
    tempo.charge({
      getClient: () => tempoRpcClient,
      recipient,
      testnet: true,
    }),
  ],
  secretKey: process.env.MPP_SECRET_KEY ?? "tempo-bench-mpp-secret-key-000000001",
});

function jsonResponse(body: unknown, status = 200) {
  return Response.json(body, { status });
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);

  if (request.method === "GET" && url.pathname === freePath) {
    return NodeListener.sendResponse(response, jsonResponse({ ok: true, endpoint: "free" }));
  }

  if (request.method === "GET" && url.pathname === paidPath) {
    const result = await mppx.compose(
      ["tempo/charge", {
        amount: chargeAmount,
        currency: pathUsd,
        description: "Paid JSON with pathUSD",
      }],
      ["tempo/charge", {
        amount: chargeAmount,
        currency: usdc,
        description: "Paid JSON with USDC",
      }],
    )(ServerRequest.fromNodeListener(request, response));
    if (result.status === 402) return NodeListener.sendResponse(response, result.challenge);
    return NodeListener.sendResponse(
      response,
      result.withReceipt(jsonResponse({ ok: true, endpoint: "paid" })),
    );
  }

  return NodeListener.sendResponse(response, jsonResponse({ ok: false, error: "not_found" }, 404));
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
