import { writeFileSync } from "node:fs";
import http from "node:http";
import { Hono } from "hono";
import { Mppx, tempo } from "mppx/hono";
import { NodeListener, Request as ServerRequest } from "mppx/server";

const port = Number(process.env.PORT ?? "3000");
const freePath = "/free";
const paidPath = "/paid";
const pathUsd = "0x20c0000000000000000000000000000000000000";
const recipient = (process.env.RECIPIENT_ADDRESS ?? "0x1111111111111111111111111111111111111111") as `0x${string}`;
const chargeAmount = process.env.MPP_CHARGE_AMOUNT ?? "0.01";

const app = new Hono();
const mppx = Mppx.create({
  methods: [
    tempo.charge({
      recipient,
      testnet: true,
    }),
  ],
  secretKey: process.env.MPP_SECRET_KEY ?? "tempo-bench-mpp-secret-key-000000001",
});

app.get(freePath, (c) => c.json({ ok: true, endpoint: "free" }));
app.get(
  paidPath,
  mppx.charge({ amount: chargeAmount, currency: pathUsd, description: "Paid JSON" }),
  (c) => c.json({ ok: true, endpoint: "paid" }),
);
app.notFound((c) => c.json({ ok: false, error: "not_found" }, 404));

const server = http.createServer(async (request, response) => {
  const fetchRequest = ServerRequest.fromNodeListener(request, response);
  return NodeListener.sendResponse(response, await app.fetch(fetchRequest));
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
