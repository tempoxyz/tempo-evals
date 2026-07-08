import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createMcpExpressApp } from "@modelcontextprotocol/sdk/server/express.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import * as z from "zod/v4";

const root = dirname(fileURLToPath(import.meta.url));

const docs = [
  {
    slug: "transfer-with-memo",
    title: "Tempo TIP-20 Transfer With Memo",
    uri: "tempo://docs/transfer-with-memo",
    text: readFileSync(join(root, "docs/transfer-with-memo.md"), "utf8"),
  },
];

function createServer() {
  const server = new McpServer(
    {
      name: "tempo-docs",
      version: "0.0.0",
    },
    {
      capabilities: {
        resources: {},
        tools: {},
      },
    },
  );

  for (const doc of docs) {
    server.registerResource(
      doc.slug,
      doc.uri,
      {
        title: doc.title,
        description: `Tempo documentation for ${doc.slug}`,
        mimeType: "text/markdown",
      },
      async () => ({
        contents: [
          {
            uri: doc.uri,
            mimeType: "text/markdown",
            text: doc.text,
          },
        ],
      }),
    );
  }

  server.registerTool(
    "search_tempo_docs",
    {
      title: "Search Tempo Docs",
      description: "Search local Tempo docs for integration guidance.",
      inputSchema: {
        query: z.string().describe("Search query, for example transferWithMemo"),
      },
      annotations: {
        readOnlyHint: true,
        openWorldHint: false,
      },
    },
    async ({ query }) => {
      const terms = query
        .toLowerCase()
        .split(/\W+/)
        .filter(Boolean);

      const results = docs
        .map((doc) => {
          const haystack = `${doc.title}\n${doc.text}`.toLowerCase();
          const score = terms.reduce((sum, term) => {
            return sum + (haystack.match(new RegExp(term, "g"))?.length ?? 0);
          }, 0);
          return {
            slug: doc.slug,
            title: doc.title,
            uri: doc.uri,
            score,
            snippet: doc.text.split("\n").slice(0, 8).join("\n"),
          };
        })
        .filter((doc) => doc.score > 0)
        .sort((a, b) => b.score - a.score);

      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(results, null, 2),
          },
        ],
      };
    },
  );

  server.registerTool(
    "get_tempo_doc",
    {
      title: "Get Tempo Doc",
      description: "Fetch a Tempo documentation page by slug.",
      inputSchema: {
        slug: z.enum(["transfer-with-memo"]).describe("Documentation slug"),
      },
      annotations: {
        readOnlyHint: true,
        openWorldHint: false,
      },
    },
    async ({ slug }) => {
      const doc = docs.find((candidate) => candidate.slug === slug);
      if (!doc) throw new Error(`Unknown Tempo docs slug: ${slug}`);

      return {
        content: [
          {
            type: "text",
            text: doc.text,
          },
        ],
      };
    },
  );

  return server;
}

const app = createMcpExpressApp();

app.get("/health", (_req, res) => {
  res.status(200).json({ ok: true });
});

app.post("/mcp", async (req, res) => {
  const server = createServer();

  try {
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
    });

    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);

    res.on("close", () => {
      transport.close();
      server.close();
    });
  } catch (error) {
    console.error("Error handling MCP request:", error);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        error: {
          code: -32603,
          message: "Internal server error",
        },
        id: null,
      });
    }
  }
});

app.get("/mcp", (_req, res) => {
  res.writeHead(405).end(
    JSON.stringify({
      jsonrpc: "2.0",
      error: {
        code: -32000,
        message: "Method not allowed.",
      },
      id: null,
    }),
  );
});

const port = Number(process.env.PORT ?? "3000");

app.listen(port, (error) => {
  if (error) {
    console.error("Failed to start Tempo docs MCP server:", error);
    process.exit(1);
  }

  console.log(`Tempo docs MCP server listening on port ${port}`);
});
