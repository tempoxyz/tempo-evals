import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";

async function main() {
  const workspace = process.env.TEMPO_BENCH_WORKSPACE ?? "/app";
  const workspaceRequire = createRequire(`${workspace}/package.json`);
  const globalRequire = createRequire(
    `${execFileSync("npm", ["root", "--global"], { encoding: "utf8" }).trim()}/package.json`,
  );
  const { Client } = await import(
    globalRequire.resolve("@modelcontextprotocol/sdk/client/index.js"),
  );
  const { StreamableHTTPClientTransport } = await import(
    globalRequire.resolve("@modelcontextprotocol/sdk/client/streamableHttp.js"),
  );
  const { McpClient } = await import(workspaceRequire.resolve("mppx/mcp/client"));
  const { tempo } = await import(workspaceRequire.resolve("mppx/client"));
  const { createClient, http } = await import(workspaceRequire.resolve("viem"));
  const { privateKeyToAccount } = await import(
    workspaceRequire.resolve("viem/accounts"),
  );
  const { Chain } = await import(workspaceRequire.resolve("viem/tempo"));

  const client = new Client({
    name: "tempo-bench-verifier",
    version: "1.0.0",
  });
  const transport = new StreamableHTTPClientTransport(
    new URL(process.env.TEMPO_MPP_MCP_URL),
  );
  await client.connect(transport);

  const free = await client.callTool({
    name: process.env.TEMPO_MPP_FREE_TOOL,
    arguments: {},
  });

  let unpaid;
  try {
    await client.callTool({
      name: process.env.TEMPO_MPP_PAID_TOOL,
      arguments: {},
    });
    unpaid = { paymentRequired: false };
  } catch (error) {
    unpaid = {
      paymentRequired: McpClient.isPaymentRequiredError(error),
      httpStatus: error.data?.httpStatus,
      challengeCount: error.data?.challenges?.length ?? 0,
      method: error.data?.challenges?.[0]?.method,
      intent: error.data?.challenges?.[0]?.intent,
    };
  }

  const account = privateKeyToAccount(process.env.TEMPO_MPP_PAYER_PRIVATE_KEY);
  const viemClient = createClient({
    account,
    chain: Chain.testnet,
    transport: http(process.env.MPPX_RPC_URL),
  });

  McpClient.wrap(client, {
    methods: [
      tempo({
        account,
        expectedChainId: Number(process.env.TEMPO_MPP_CHAIN_ID),
        getClient: () => viemClient,
      }),
    ],
    onPaymentRequired: () => true,
  });

  const paid = await client.callTool({
    name: process.env.TEMPO_MPP_PAID_TOOL,
    arguments: {},
  });
  await client.close();

  console.log(
    JSON.stringify({
      free: {
        hasContent: Array.isArray(free.content) && free.content.length > 0,
      },
      unpaid,
      paid: {
        hasContent: Array.isArray(paid.content) && paid.content.length > 0,
        hasReceipt: Boolean(paid.receipt),
        receipt: paid.receipt,
      },
    }),
  );
}

main();
