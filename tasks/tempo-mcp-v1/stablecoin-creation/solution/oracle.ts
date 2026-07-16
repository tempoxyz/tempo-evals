// AUTO-GENERATED INTO EACH MCP TASK BY npm run sync. DO NOT EDIT COPIES.
import { writeFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

type McpPayload = {
  error?: unknown;
  result?: unknown;
};

type Lookup = {
  tool: string;
  arguments: Record<string, unknown>;
};

type OracleTask = {
  lookups: Lookup[];
  observation: { lookup: number; count: number; subject?: string };
  docsQuery: string;
};

const endpoint = process.env.TEMPO_MCP_ORACLE_URL ?? "http://tempo-mcp-direct:8787/mcp";
const docsTool = process.env.TEMPO_MCP_ORACLE_DOCS_TOOL ?? "docs_search";
const taskName = process.argv[2];
const historicalWindow = {
  "timestamp.from": "2026-07-10T22:30:00Z",
  "timestamp.to": "2026-07-10T22:40:00Z",
  include: ["receipt"],
  limit: 5,
};

const tasks: Record<string, OracleTask> = {
  "access-keys": {
    lookups: [{ tool: "v1_transactions_get", arguments: historicalWindow }],
    observation: { lookup: 0, count: 2 },
    docsQuery: "Tempo access keys and fee sponsorship",
  },
  "batched-transfers": {
    lookups: [{ tool: "v1_transactions_get", arguments: historicalWindow }],
    observation: { lookup: 0, count: 1 },
    docsQuery: "Tempo multi-payment batched transfers",
  },
  "dex-swap": {
    lookups: [{ tool: "v1_fee-amm_pools", arguments: { include: ["token"], limit: 5 } }],
    observation: { lookup: 0, count: 1 },
    docsQuery: "Tempo Fee AMM fee token payments",
  },
  "faucet-funding": {
    lookups: [
      {
        tool: "v1_addresses_address_activities",
        arguments: { address: "0x385193793fe875cd9f2341409563932023fb4fab", limit: 20 },
      },
      {
        tool: "v1_addresses_address_balances",
        arguments: { address: "0x385193793fe875cd9f2341409563932023fb4fab", limit: 20 },
      },
    ],
    observation: {
      lookup: 0,
      count: 1,
      subject: "0x385193793fe875cd9f2341409563932023fb4fab",
    },
    docsQuery: "Tempo account activity and funding",
  },
  "fee-token-and-payer": {
    lookups: [
      {
        tool: "v1_transactions_transactionHash_get",
        arguments: {
          transactionHash: "0x52420cada2074e5ca33c381f39acb0c7849522f916a516ccad2ab936306198ec",
          include: ["feeToken", "receipt"],
        },
      },
    ],
    observation: {
      lookup: 0,
      count: 1,
      subject: "0x52420cada2074e5ca33c381f39acb0c7849522f916a516ccad2ab936306198ec",
    },
    docsQuery: "Tempo fee token and fee payer",
  },
  "fee-token-configuration": {
    lookups: [
      {
        tool: "v1_transactions_get",
        arguments: { ...historicalWindow, feeToken: "0x20c000000000000000000000b9537d11c60e8b50" },
      },
      { tool: "v1_fee-amm_pools", arguments: { include: ["token"], limit: 5 } },
    ],
    observation: { lookup: 0, count: 1 },
    docsQuery: "Tempo fee token configuration",
  },
  "passkey-account": {
    lookups: [
      {
        tool: "v1_addresses_address_activities",
        arguments: { address: "0xbe058e1c4df8a4366a387bf595b284246a93039e", limit: 10 },
      },
    ],
    observation: {
      lookup: 0,
      count: 1,
      subject: "0xbe058e1c4df8a4366a387bf595b284246a93039e",
    },
    docsQuery: "Tempo passkey account authorization",
  },
  "policy-authorization": {
    lookups: [{ tool: "v1_transactions_get", arguments: historicalWindow }],
    observation: { lookup: 0, count: 1 },
    docsQuery: "Tempo access key authorization and fee sponsorship",
  },
  "stablecoin-creation": {
    lookups: [
      {
        tool: "v1_tokens_get",
        arguments: { verified: true, currency: "USD", include: ["holderCount"], limit: 5 },
      },
      {
        tool: "v1_tokens_token_transactions",
        arguments: { token: "0x20c0000000000000000000000000000000000000", limit: 5 },
      },
    ],
    observation: { lookup: 0, count: 5 },
    docsQuery: "Tempo TIP-20 token specification",
  },
  "tip20-transfer-memo": {
    lookups: [
      {
        tool: "v1_addresses_address_activities",
        arguments: { address: "0x385193793fe875cd9f2341409563932023fb4fab", limit: 20 },
      },
    ],
    observation: {
      lookup: 0,
      count: 1,
      subject: "0x385193793fe875cd9f2341409563932023fb4fab",
    },
    docsQuery: "Tempo TIP-20 transfer memo",
  },
  "transaction-status": {
    lookups: [{ tool: "v1_blocks_get", arguments: { limit: 5 } }],
    observation: { lookup: 0, count: 1 },
    docsQuery: "Tempo T7 upgrade",
  },
  "wallet-client": {
    lookups: [{ tool: "v1_transactions_get", arguments: historicalWindow }],
    observation: { lookup: 0, count: 1 },
    docsQuery: "Tempo wallet client transaction flow",
  },
};

function parseResponse(text: string): McpPayload {
  if (!text.startsWith("event:")) return JSON.parse(text) as McpPayload;
  const data = text
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).trim())
    .filter(Boolean)
    .at(-1);
  if (!data) throw new Error("MCP response did not include an event payload");
  return JSON.parse(data) as McpPayload;
}

function firstUrl(value: unknown): string {
  const match = JSON.stringify(value).match(/https:\/\/(?:docs|developers)\.tempo\.xyz[^"\\\s]*/);
  return match?.[0] ?? "https://docs.tempo.xyz/";
}

function toolValue(result: any): any {
  if (result?.isError) throw new Error(`MCP tool failed: ${JSON.stringify(result)}`);
  const text = result?.content?.find((item: any) => item?.type === "text")?.text;
  if (typeof text !== "string") return result?.structuredContent ?? result;
  const value = JSON.parse(text);
  if (value?.error) throw new Error(`MCP tool failed: ${JSON.stringify(value.error)}`);
  return value;
}

function records(value: any): any[] {
  if (Array.isArray(value?.data)) return value.data;
  return value && typeof value === "object" ? [value] : [];
}

function recordSubject(record: any): string {
  for (const key of ["hash", "transactionHash", "address", "id", "number", "symbol"]) {
    if (typeof record?.[key] === "string" || typeof record?.[key] === "number") {
      return String(record[key]);
    }
  }
  return "MCP response record";
}

export function docsRequest(tool: string, query: string): { name: string; arguments: { name: string; arguments: Record<string, unknown> } } {
  let args: Record<string, unknown>;
  if (tool === "docs_search") {
    args = { query, max_results: 1 };
  } else if (tool === "docs_code") {
    args = {
      code: `async () => codemode.search({ query: ${JSON.stringify(query)}, source: "tempo", max_results: 1 })`,
    };
  } else {
    throw new Error(`Unknown MCP oracle docs tool: ${tool}`);
  }
  return { name: "call_write_tool", arguments: { name: tool, arguments: args } };
}

async function main(): Promise<void> {
  const task = taskName ? tasks[taskName] : undefined;
  if (!task || !taskName) throw new Error(`Unknown MCP oracle task: ${taskName}`);

  let sessionId: string | null = null;
  let id = 1;
  async function request(method: string, params: Record<string, unknown>): Promise<any> {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        accept: "application/json, text/event-stream",
        "content-type": "application/json",
        "mcp-protocol-version": "2025-06-18",
        ...(sessionId ? { "mcp-session-id": sessionId } : {}),
      },
      body: JSON.stringify({ jsonrpc: "2.0", id: id++, method, params }),
    });
    sessionId = response.headers.get("mcp-session-id") ?? sessionId;
    const payload = parseResponse(await response.text());
    if (!response.ok || payload.error) {
      throw new Error(`MCP ${method} failed: ${JSON.stringify(payload.error ?? payload)}`);
    }
    return payload.result;
  }

  await request("initialize", {
    protocolVersion: "2025-06-18",
    capabilities: {},
    clientInfo: { name: "tempo-bench-oracle", version: "1" },
  });
  const results: any[] = [];
  for (const lookup of task.lookups) {
    const result = await request("tools/call", {
      name: "call_read_tool",
      arguments: { name: lookup.tool, arguments: lookup.arguments },
    });
    results.push(toolValue(result));
  }
  const docs = toolValue(
    await request("tools/call", docsRequest(docsTool, task.docsQuery)),
  );
  const evidence = task.lookups.map(({ tool }) => ({
    source: `mcp://tempo/${tool}`,
    claim: `The ${tool} lookup completed for the task's fixed oracle input.`,
  }));
  const answer = {
    summary: `${taskName} oracle completed its fixed data lookups and Tempo documentation search.`,
    observations: records(results[task.observation.lookup])
      .slice(0, task.observation.count)
      .map((record: any) => ({
        subject: task.observation.subject ?? recordSubject(record),
        details: `${task.lookups[task.observation.lookup].tool} returned ${JSON.stringify(record)}.`,
        evidence_refs: [task.observation.lookup],
      })),
    inferences: [
      {
        claim: `The observations are consistent with the documented ${task.docsQuery} behavior.`,
        basis: "Fixed MCP data lookups and a Tempo documentation search.",
        evidence_refs: evidence.map((_, index) => index),
      },
    ],
    sources: [firstUrl(docs)],
    evidence,
  };
  writeFileSync("/app/answer.json", `${JSON.stringify(answer)}\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  await main();
}
