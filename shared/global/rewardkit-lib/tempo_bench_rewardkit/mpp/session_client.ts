import { createRequire } from "node:module";

async function main() {
  const require = createRequire("/opt/tempo-bench/verifier/package.json");
  const { tempo } = await import(require.resolve("mppx/client"));
  const { createClient, http } = await import(require.resolve("viem"));
  const { privateKeyToAccount } = await import(require.resolve("viem/accounts"));
  const { Actions, Chain } = await import(require.resolve("viem/tempo"));

  const account = privateKeyToAccount(process.env.TEMPO_MPP_PAYER_PRIVATE_KEY as `0x${string}`);
  const client = createClient({
    account,
    chain: Chain.testnet,
    pollingInterval: 1_000,
    transport: http(process.env.MPPX_RPC_URL),
  });

  await Actions.faucet.fundSync(client, { account, timeout: 60_000 });
  const session = tempo.session.manager({ client, maxDeposit: "0.02" });
  const response = await session.fetch(process.env.TEMPO_MPP_SESSION_URL!, {
    headers: { accept: "application/json" },
  });
  const receiptHeader = response.headers.get("payment-receipt");
  if (!response.ok) throw new Error(`session request returned ${response.status}`);
  if (!receiptHeader) throw new Error("session response did not include Payment-Receipt");
  await response.json();
  const closeReceipt = await session.close();

  console.log(
    JSON.stringify({
      status: response.status,
      json: true,
      hasReceipt: true,
      closeReceipt,
      closeSucceeded: true,
    }),
  );
}

main();
