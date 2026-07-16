import http from "node:http";
import { writeFileSync } from "node:fs";
import { Mppx, NodeListener, Request as ServerRequest, evm, tempo } from "mppx/server";
import { tempoRpcClient } from "./tempo-rpc.js";

const port = Number(process.env.PORT ?? "3000");
const mppPaidPath = "/mpp";
const x402PaidPath = "/x402";
const pathUsd = "0x20c0000000000000000000000000000000000000";
const recipient = (process.env.RECIPIENT_ADDRESS ?? "0x1111111111111111111111111111111111111111") as `0x${string}`;
const chargeAmount = process.env.MPP_CHARGE_AMOUNT ?? "0.01";

const mppx = Mppx.create({
  methods: [
    tempo.charge({
      currency: pathUsd,
      getClient: () => tempoRpcClient,
      recipient,
      testnet: true,
    }),
    evm.charge({
      currency: evm.assets.baseSepolia.USDC,
      recipient,
      x402: {
        facilitator: process.env.X402_FACILITATOR_URL ?? "https://facilitator.x402.rs",
      },
    }),
  ],
  secretKey: process.env.MPP_SECRET_KEY ?? "tempo-bench-mpp-secret-key-000000001",
});

function jsonResponse(body: unknown, status = 200) {
  return Response.json(body, { status });
}

const server = http.createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://${request.headers.host ?? "localhost"}`);
  const fetchRequest = ServerRequest.fromNodeListener(request, response);

  if (request.method === "GET" && url.pathname === mppPaidPath) {
    const result = await mppx.tempo.charge({
      amount: chargeAmount,
      description: "MPP pathUSD JSON",
    })(fetchRequest);
    if (result.status === 402) {
      const headers = new Headers(result.challenge.headers);
      headers.set("x-tempo-currency", pathUsd);
      return NodeListener.sendResponse(
        response,
        new Response(await result.challenge.text(), { status: 402, headers }),
      );
    }
    return NodeListener.sendResponse(
      response,
      result.withReceipt(jsonResponse({ ok: true, endpoint: "mpp" })),
    );
  }

  if (request.method === "GET" && url.pathname === x402PaidPath) {
    const result = await mppx.evm.charge({
      amount: chargeAmount,
      description: "x402 USDC JSON",
    })(fetchRequest);
    if (result.status === 402) {
      const headers = new Headers(result.challenge.headers);
      headers.set("x402-currency", evm.assets.baseSepolia.USDC.address);
      return NodeListener.sendResponse(
        response,
        new Response(await result.challenge.text(), { status: 402, headers }),
      );
    }
    return NodeListener.sendResponse(
      response,
      result.withReceipt(jsonResponse({ ok: true, endpoint: "x402" })),
    );
  }

  return NodeListener.sendResponse(response, jsonResponse({ ok: false, error: "not_found" }, 404));
});

server.listen(port, "0.0.0.0", () => {
  writeFileSync(
    "out.json",
    `${JSON.stringify({
      mppPaidUrl: `http://127.0.0.1:${port}${mppPaidPath}`,
      x402PaidUrl: `http://127.0.0.1:${port}${x402PaidPath}`,
    })}\n`,
  );
});
