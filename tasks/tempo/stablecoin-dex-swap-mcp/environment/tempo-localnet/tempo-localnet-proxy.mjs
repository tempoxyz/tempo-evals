// AUTO-GENERATED FROM shared/docker/tempo-localnet/tempo-localnet-proxy.mjs BY npm run sync. DO NOT EDIT MANUALLY.
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import {
  createPublicClient,
  createWalletClient,
  defineChain,
  http,
  parseAbi,
} from "viem";
import { privateKeyToAccount } from "viem/accounts";

const listenHost = "0.0.0.0";
const listenPort = 8545;
const tempoRpcUrl = "http://127.0.0.1:8546";
const faucetPrivateKey =
  process.env.TEMPO_LOCALNET_FAUCET_PRIVATE_KEY ??
  "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80";
const faucetAmount = BigInt(process.env.TEMPO_LOCALNET_FAUCET_AMOUNT ?? "1000000000000");
const faucetTokens = (
  process.env.TEMPO_LOCALNET_FAUCET_TOKENS ??
  [
    "0x20c0000000000000000000000000000000000000",
    "0x20c0000000000000000000000000000000000001",
    "0x20c0000000000000000000000000000000000002",
    "0x20c0000000000000000000000000000000000003",
  ].join(",")
)
  .split(",")
  .map((token) => token.trim())
  .filter(Boolean);

const tokenAbi = parseAbi(["function transfer(address to,uint256 amount) returns (bool)"]);
const faucetAccount = privateKeyToAccount(faucetPrivateKey);
let clientPromise;

const tempo = spawn(
  "tempo",
  [
    "node",
    "--dev",
    "--http",
    "--http.addr",
    "127.0.0.1",
    "--http.port",
    "8546",
    "--http.api",
    "all",
    "--ipcdisable",
    "--disable-discovery",
    "--disable-auth-server",
    "--datadir",
    "/tmp/tempo-dev",
    "--log.stdout.filter",
    "info",
  ],
  { stdio: ["ignore", "inherit", "inherit"] },
);

process.on("SIGTERM", () => {
  tempo.kill("SIGTERM");
  process.exit(0);
});
process.on("SIGINT", () => {
  tempo.kill("SIGINT");
  process.exit(0);
});
tempo.on("exit", (code, signal) => {
  if (signal !== "SIGTERM" && signal !== "SIGINT") process.exit(code ?? 1);
});

function jsonRpcResult(id, result) {
  return { jsonrpc: "2.0", id, result };
}

function jsonRpcError(id, code, message) {
  return { jsonrpc: "2.0", id, error: { code, message } };
}

async function postToTempo(payload) {
  const response = await fetch(tempoRpcUrl, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  return response.json();
}

async function waitForTempo() {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    try {
      const response = await postToTempo({
        jsonrpc: "2.0",
        id: 1,
        method: "eth_chainId",
        params: [],
      });
      if (response.result) return Number(BigInt(response.result));
    } catch {
      // Retry until the child node accepts RPC.
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("Tempo localnet RPC did not start");
}

async function clients() {
  if (!clientPromise) {
    clientPromise = waitForTempo().then((chainId) => {
      const chain = defineChain({
        id: chainId,
        name: "Tempo Localnet",
        nativeCurrency: { name: "USD", symbol: "USD", decimals: 6 },
        rpcUrls: { default: { http: [tempoRpcUrl] } },
      });
      const publicClient = createPublicClient({ chain, transport: http(tempoRpcUrl) });
      const walletClient = createWalletClient({
        account: faucetAccount,
        chain,
        transport: http(tempoRpcUrl),
      });
      return { publicClient, walletClient };
    });
  }
  return clientPromise;
}

async function fundAddress(id, params) {
  const [recipient] = params ?? [];
  if (typeof recipient !== "string" || !/^0x[0-9a-fA-F]{40}$/.test(recipient)) {
    return jsonRpcError(id, -32602, "tempo_fundAddress requires one address parameter");
  }

  const { publicClient, walletClient } = await clients();
  const hashes = [];
  let nonce = await publicClient.getTransactionCount({
    address: faucetAccount.address,
    blockTag: "pending",
  });
  for (const token of faucetTokens) {
    const hash = await walletClient.writeContract({
      address: token,
      abi: tokenAbi,
      functionName: "transfer",
      args: [recipient, faucetAmount],
      nonce,
    });
    nonce += 1;
    hashes.push(hash);
  }
  return jsonRpcResult(id, hashes);
}

async function handleRpc(payload) {
  if (Array.isArray(payload)) return Promise.all(payload.map(handleRpc));
  if (payload?.method === "tempo_fundAddress") {
    try {
      return await fundAddress(payload.id ?? null, payload.params);
    } catch (error) {
      return jsonRpcError(payload.id ?? null, -32603, error?.message ?? String(error));
    }
  }
  return postToTempo(payload);
}

createServer(async (request, response) => {
  if (request.method !== "POST") {
    response.writeHead(405, { "content-type": "application/json" });
    response.end(JSON.stringify({ error: "method not allowed" }));
    return;
  }

  let body = "";
  request.setEncoding("utf8");
  request.on("data", (chunk) => {
    body += chunk;
  });
  request.on("end", async () => {
    try {
      const payload = JSON.parse(body);
      const result = await handleRpc(payload);
      response.writeHead(200, { "content-type": "application/json" });
      response.end(JSON.stringify(result));
    } catch (error) {
      response.writeHead(500, { "content-type": "application/json" });
      response.end(JSON.stringify(jsonRpcError(null, -32603, error?.message ?? String(error))));
    }
  });
}).listen(listenPort, listenHost);
