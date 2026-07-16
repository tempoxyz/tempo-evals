import { createClient, http } from "viem";
import { Chain } from "viem/tempo";

export const tempoRpcTransport = http(process.env.MPPX_RPC_URL, {
  retryCount: 0,
  timeout: 65_000,
});
export const tempoRpcClient = createClient({
  chain: Chain.testnet,
  transport: tempoRpcTransport,
});
