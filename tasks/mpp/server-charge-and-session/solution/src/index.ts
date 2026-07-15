import http from "node:http";
import { writeFileSync } from "node:fs";
import { Mppx, NodeListener, Request as ServerRequest, tempo } from "mppx/server";
import { createClient } from "viem";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";
import { Actions, Chain } from "viem/tempo";
import { tempoRpcTransport } from "./tempo-rpc.js";

const port = Number(process.env.PORT ?? "3000");
const chargePath = "/charge";
const sessionPath = "/session";
const pathUsd = "0x20c0000000000000000000000000000000000000";
const recipient = (process.env.RECIPIENT_ADDRESS ?? "0x1111111111111111111111111111111111111111") as `0x${string}`;
const chargeAmount = process.env.MPP_CHARGE_AMOUNT ?? "0.01";
const account = privateKeyToAccount(generatePrivateKey());
const client = createClient({
  account,
  chain: Chain.testnet,
  pollingInterval: 1_000,
  transport: tempoRpcTransport,
});

await Actions.faucet.fundSync(client, { account, timeout: 60_000 });

const mppx = Mppx.create({
  methods: [
    tempo.charge({
      currency: pathUsd,
      getClient: () => client,
      recipient,
      testnet: true,
    }),
    tempo.session({
      account,
      currency: pathUsd,
      getClient: () => client,
      recipient: account.address,
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

  if (request.method === "GET" && url.pathname === chargePath) {
    const result = await mppx.charge({
      amount: chargeAmount,
      description: "Charge JSON",
    })(fetchRequest);
    if (result.status === 402) return NodeListener.sendResponse(response, result.challenge);
    return NodeListener.sendResponse(
      response,
      result.withReceipt(jsonResponse({ ok: true, endpoint: "charge" })),
    );
  }

  if (url.pathname === sessionPath) {
    const result = await mppx.session({
      amount: chargeAmount,
      unitType: "request",
    })(fetchRequest);
    if (result.status === 402) return NodeListener.sendResponse(response, result.challenge);
    return NodeListener.sendResponse(
      response,
      result.withReceipt(jsonResponse({ ok: true, endpoint: "session" })),
    );
  }

  return NodeListener.sendResponse(response, jsonResponse({ ok: false, error: "not_found" }, 404));
});

server.listen(port, "0.0.0.0", () => {
  writeFileSync(
    "out.json",
    `${JSON.stringify({
      chargeUrl: `http://127.0.0.1:${port}${chargePath}`,
      sessionUrl: `http://127.0.0.1:${port}${sessionPath}`,
    })}\n`,
  );
});
