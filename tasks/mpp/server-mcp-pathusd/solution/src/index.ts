import { writeFileSync } from "node:fs";
import { createMcpExpressApp } from "@modelcontextprotocol/sdk/server/express.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { Transport as MppMcpTransport } from "mppx/mcp/server";
import { Mppx, tempo } from "mppx/server";
import { tempoRpcClient } from "./tempo-rpc.js";

const port = Number(process.env.PORT ?? "3000");
const mcpPath = "/mcp";
const freeTool = "free_ping";
const paidTool = "paid_summary";
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
  ],
  secretKey: process.env.MPP_SECRET_KEY ?? "stable-bench-mpp-secret-key-000000001",
  transport: MppMcpTransport.mcpSdk(),
});

function createServer() {
  const server = new McpServer(
    {
      name: "tempo-mpp-paid-tools",
      version: "1.0.0",
    },
    {
      capabilities: {
        tools: {},
      },
    },
  );

  server.registerTool(
    freeTool,
    {
      title: "Free Ping",
      description: "Return free JSON-like MCP content.",
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        openWorldHint: false,
      },
    },
    async () => ({
      content: [{ type: "text", text: JSON.stringify({ ok: true, tool: freeTool }) }],
    }),
  );

  server.registerTool(
    paidTool,
    {
      title: "Paid Summary",
      description: "Return paid MCP content after a pathUSD charge.",
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        openWorldHint: false,
      },
    },
    async (_args, extra) => {
      const result = await mppx.charge({
        amount: chargeAmount,
        description: "Paid MCP tool",
      })(extra);
      if (result.status === 402) throw result.challenge;
      return result.withReceipt({
        content: [{ type: "text", text: JSON.stringify({ ok: true, tool: paidTool }) }],
      });
    },
  );

  return server;
}

const app = createMcpExpressApp({ host: "0.0.0.0" });

app.get("/health", (_request: any, response: any) => {
  response.status(200).json({ ok: true });
});

app.post(mcpPath, async (request: any, response: any) => {
  const server = createServer();
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
  });
  try {
    await server.connect(transport);
    await transport.handleRequest(request, response, request.body);
  } finally {
    response.on("close", () => {
      void transport.close();
      void server.close();
    });
  }
});

app.listen(port, "0.0.0.0", () => {
  writeFileSync(
    "out.json",
    `${JSON.stringify({
      mcpUrl: `http://127.0.0.1:${port}${mcpPath}`,
      freeTool,
      paidTool,
    })}\n`,
  );
});
