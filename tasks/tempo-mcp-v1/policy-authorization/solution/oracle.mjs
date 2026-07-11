// AUTO-GENERATED INTO EACH MCP TASK BY npm run sync. DO NOT EDIT COPIES.
import { writeFileSync } from "node:fs";

const endpoint = process.env.TEMPO_MCP_ORACLE_URL ?? "http://tempo-mcp-direct:8787/mcp";
const taskName = process.argv[2];
const historicalWindow = {
  "timestamp.from": "2026-07-10T22:30:00Z",
  "timestamp.to": "2026-07-10T22:40:00Z",
  include: ["receipt"],
  limit: 5,
};

const tasks = {
  "access-keys": {
    tool: "v1_transactions_get",
    arguments: historicalWindow,
    docsQuery: "Tempo access keys and fee sponsorship",
  },
  "batched-transfers": {
    tool: "v1_transactions_get",
    arguments: historicalWindow,
    docsQuery: "Tempo multi-payment batched transfers",
  },
  "dex-swap": {
    tool: "v1_fee-amm_pools",
    arguments: { include: ["token"], limit: 5 },
    docsQuery: "Tempo Fee AMM fee token payments",
  },
  "faucet-funding": {
    tool: "v1_addresses_address_activities",
    arguments: { address: "0x385193793fe875cd9f2341409563932023fb4fab", limit: 20 },
    docsQuery: "Tempo account activity and funding",
  },
  "fee-token-and-payer": {
    tool: "v1_transactions_transactionHash_get",
    arguments: {
      transactionHash: "0x52420cada2074e5ca33c381f39acb0c7849522f916a516ccad2ab936306198ec",
      include: ["feeToken", "receipt"],
    },
    docsQuery: "Tempo fee token and fee payer",
  },
  "fee-token-configuration": {
    tool: "v1_transactions_get",
    arguments: { ...historicalWindow, feeToken: "0x20c000000000000000000000b9537d11c60e8b50" },
    docsQuery: "Tempo fee token configuration",
  },
  "passkey-account": {
    tool: "v1_addresses_address_activities",
    arguments: { address: "0xbe058e1c4df8a4366a387bf595b284246a93039e", limit: 10 },
    docsQuery: "Tempo passkey account authorization",
  },
  "policy-authorization": {
    tool: "v1_transactions_get",
    arguments: historicalWindow,
    docsQuery: "Tempo access key authorization and fee sponsorship",
  },
  "stablecoin-creation": {
    tool: "v1_tokens_get",
    arguments: { verified: true, currency: "USD", include: ["holderCount"], limit: 5 },
    docsQuery: "Tempo TIP-20 token specification",
  },
  "tip20-transfer-memo": {
    tool: "v1_transfers",
    arguments: {
      address: "0x385193793fe875cd9f2341409563932023fb4fab",
      ...historicalWindow,
      include: ["token", "memo"],
    },
    docsQuery: "Tempo TIP-20 transfer memo",
  },
  "transaction-status": {
    tool: "v1_transactions_get",
    arguments: {
      "timestamp.from": "2026-07-10T22:02:00Z",
      "timestamp.to": "2026-07-10T22:03:00Z",
      include: ["receipt"],
      limit: 5,
    },
    docsQuery: "Tempo T7 upgrade",
  },
  "wallet-client": {
    tool: "v1_transactions_get",
    arguments: historicalWindow,
    docsQuery: "Tempo wallet client transaction flow",
  },
};

function parseResponse(text) {
  if (!text.startsWith("event:")) return JSON.parse(text);
  const data = text
    .split(/\r?\n/)
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice("data:".length).trim())
    .filter(Boolean)
    .at(-1);
  if (!data) throw new Error("MCP response did not include an event payload");
  return JSON.parse(data);
}

function firstUrl(value) {
  const match = JSON.stringify(value).match(/https:\/\/(?:docs|developers)\.tempo\.xyz[^"\\\s]*/);
  return match?.[0] ?? "https://docs.tempo.xyz/";
}

async function main() {
  const task = tasks[taskName];
  if (!task) throw new Error(`Unknown MCP oracle task: ${taskName}`);

  let sessionId;
  let id = 1;
  async function request(method, params) {
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
  const data = await request("tools/call", { name: task.tool, arguments: task.arguments });
  const docs = await request("tools/call", {
    name: "docs_search",
    arguments: { query: task.docsQuery, max_results: 1 },
  });
  const evidenceSource = `mcp://tempo/${task.tool}`;
  const answer = {
    answer: `${taskName} oracle completed the fixed ${task.tool} lookup and a Tempo documentation search for ${task.docsQuery}. The live response is linked to the evidence entry.`,
    sources: [firstUrl(docs)],
    evidence: [
      {
        source: evidenceSource,
        claim: `The ${task.tool} lookup completed for the task's fixed oracle input.`,
      },
    ],
  };
  writeFileSync("/app/answer.json", `${JSON.stringify(answer)}\n`);
  void data;
}

await main();
