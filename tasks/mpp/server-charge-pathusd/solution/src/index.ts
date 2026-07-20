import http from "node:http";
import { writeFileSync } from "node:fs";
import { Mppx, tempo } from "mppx/server";
import { tempoRpcClient } from "./tempo-rpc.js";

const port = Number(process.env.PORT ?? "3000");
const freePath = "/free";
const paidPath = "/paid";
const recipient = (process.env.RECIPIENT_ADDRESS ?? "0x1111111111111111111111111111111111111111") as `0x${string}`;
const chargeAmount = process.env.MPP_CHARGE_AMOUNT ?? "0.01";

const mppx = Mppx.create({
  methods: [
    tempo({
      getClient: () => tempoRpcClient,
      recipient,
      testnet: true,
    }),
  ],
  secretKey: process.env.MPP_SECRET_KEY ?? "stable-bench-mpp-secret-key-000000001",
});

const paid = Mppx.toNodeListener(
  mppx.charge({
    amount: chargeAmount,
    description: "Paid JSON",
  }),
);

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
    const result = await paid(request, response);
    if (result.status === 402) return;
    writeJson(response, 200, { ok: true, endpoint: "paid" });
    return;
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
