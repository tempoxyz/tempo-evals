import { writeFileSync } from "node:fs";
import http from "node:http";
import { createRequire } from "node:module";

async function main() {
  const workspace = process.env.TEMPO_BENCH_WORKSPACE ?? "/app";
  const require = createRequire(`${workspace}/package.json`);
  const { Mppx, NodeListener, Request: ServerRequest, tempo } = await import(
    require.resolve("mppx/server"),
  );
  const { createClient, http: viemHttp } = await import(require.resolve("viem"));
  const { Chain } = await import(require.resolve("viem/tempo"));

  const paidPath = "/paid";
  const pathUsd = "0x20c0000000000000000000000000000000000000";
  const recipient = process.env.RECIPIENT_ADDRESS;
  const chargeAmount = process.env.MPP_CHARGE_AMOUNT ?? "0.01";
  const rpcClient = createClient({
    chain: Chain.testnet,
    transport: viemHttp(process.env.MPPX_RPC_URL, { retryCount: 0, timeout: 65_000 }),
  });

  const mppx = Mppx.create({
    methods: [
      tempo.charge({
        currency: pathUsd,
        getClient: () => rpcClient,
        recipient,
        testnet: true,
      }),
    ],
    secretKey: process.env.MPP_SECRET_KEY,
  });

  const server = http.createServer(async (request, response) => {
    const host = request.headers.host ?? "localhost";
    const url = new URL(request.url ?? "/", `http://${host}`);
    if (request.method === "GET" && url.pathname === paidPath) {
      const result = await mppx.charge({
        amount: chargeAmount,
        description: "Oracle paid JSON",
      })(ServerRequest.fromNodeListener(request, response));
      if (result.status === 402) {
        return NodeListener.sendResponse(response, result.challenge);
      }
      const body = Response.json({ ok: true, endpoint: "oracle-paid" });
      return NodeListener.sendResponse(response, result.withReceipt(body));
    }
    return NodeListener.sendResponse(
      response,
      Response.json({ ok: false, error: "not_found" }, { status: 404 }),
    );
  });

  server.listen(0, "127.0.0.1", () => {
    const address = server.address();
    writeFileSync(
      process.env.TEMPO_MPP_ORACLE_OUT,
      `${JSON.stringify({
        paidUrl: `http://127.0.0.1:${address.port}${paidPath}`,
      })}\n`,
    );
  });
}

main();
