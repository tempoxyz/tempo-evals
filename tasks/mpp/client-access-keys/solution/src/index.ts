import { writeFileSync } from "node:fs";
import { Receipt } from "mppx";
import { Mppx, tempo } from "mppx/client";
import { createClient, http } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { Chain } from "viem/tempo";

const paidUrl = process.env.PAID_URL;
const privateKey = process.env.TEMPO_MPP_PAYER_PRIVATE_KEY;

if (!paidUrl) throw new Error("PAID_URL is required");
if (!privateKey) throw new Error("TEMPO_MPP_PAYER_PRIVATE_KEY is required");

const account = privateKeyToAccount(privateKey as `0x${string}`);
const client = createClient({
  account,
  chain: Chain.testnet,
  transport: http(process.env.MPPX_RPC_URL),
});

const mppx = Mppx.create({
  methods: [
    tempo({
      account,
      expectedChainId: 42431,
      getClient: () => client,
    }),
  ],
  polyfill: false,
});

const response = await mppx.fetch(paidUrl, {
  headers: { accept: "application/json" },
});
const receiptHeader = response.headers.get("payment-receipt");
const receipt = receiptHeader ? Receipt.deserialize(receiptHeader) : null;
await response.json();

writeFileSync(
  "out.json",
  `${JSON.stringify({
    paidUrl,
    status: response.status,
    json: true,
    hasReceipt: Boolean(receiptHeader),
    receiptMethod: receipt?.method ?? "",
    receiptStatus: receipt?.status ?? "",
  })}\n`,
);
