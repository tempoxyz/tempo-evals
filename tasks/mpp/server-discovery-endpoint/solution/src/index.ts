import http from "node:http";
import { writeFileSync } from "node:fs";
import { generate } from "mppx/discovery";
import { Mppx, NodeListener, Request as ServerRequest, tempo } from "mppx/server";
import { parseUnits } from "viem";
import { tempoRpcClient } from "./tempo-rpc.js";

const port = Number(process.env.PORT ?? "3000");
const paidPath = "/paid";
const openapiPath = "/openapi.json";
const pathUsd = "0x20c0000000000000000000000000000000000000";
const recipient = (process.env.RECIPIENT_ADDRESS ?? "0x1111111111111111111111111111111111111111") as `0x${string}`;
const chargeAmount = process.env.MPP_CHARGE_AMOUNT ?? "0.01";
const chargeAmountAtomic = parseUnits(chargeAmount, 6).toString();

const mppx = Mppx.create({
  methods: [
    tempo.charge({
      currency: pathUsd,
      getClient: () => tempoRpcClient,
      recipient,
      testnet: true,
    }),
  ],
  secretKey: process.env.MPP_SECRET_KEY ?? "stable-bench-mpp-secret-key-000000001",
});

const openapi = generate(mppx, {
  info: { title: "MPP Paid API", version: "1.0.0" },
  routes: [
    {
      intent: "charge",
      method: "GET",
      options: { amount: chargeAmountAtomic, currency: pathUsd, description: "Paid JSON" },
      path: paidPath,
      summary: "Paid JSON endpoint",
    },
  ],
});

function jsonResponse(body: unknown, status = 200) {
  return Response.json(body, { status });
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);

  if (request.method === "GET" && url.pathname === openapiPath) {
    return NodeListener.sendResponse(response, jsonResponse(openapi));
  }

  if (request.method === "GET" && url.pathname === paidPath) {
    const result = await mppx.charge({
      amount: chargeAmount,
      description: "Paid JSON",
    })(ServerRequest.fromNodeListener(request, response));
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
      paidUrl: `http://127.0.0.1:${port}${paidPath}`,
      openapiUrl: `http://127.0.0.1:${port}${openapiPath}`,
    })}\n`,
  );
});
