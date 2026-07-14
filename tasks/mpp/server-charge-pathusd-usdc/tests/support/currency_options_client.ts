import { createRequire } from "node:module";

async function main() {
  const require = createRequire("/opt/tempo-bench/verifier/package.json");
  const { Challenge, Receipt } = await import(require.resolve("mppx"));
  const { Mppx, tempo } = await import(require.resolve("mppx/client"));
  const { createClient, http } = await import(require.resolve("viem"));
  const { privateKeyToAccount } = await import(require.resolve("viem/accounts"));
  const { Actions, Chain } = await import(require.resolve("viem/tempo"));
  const paidUrl = process.env.TEMPO_MPP_PAID_URL;
  const pathUsd = "0x20c0000000000000000000000000000000000000";
  const usdc = "0x20c000000000000000000000b9537d11c60E8b50".toLowerCase();

  const response = await fetch(paidUrl, { headers: { accept: "application/json" } });
  if (response.status !== 402) throw new Error(`expected 402, received ${response.status}`);
  const offers = Challenge.fromResponseList(response);
  const currencies = offers
    .filter((offer) => offer.method === "tempo" && offer.intent === "charge")
    .map((offer) => String(offer.request.currency).toLowerCase());
  if (!currencies.includes(pathUsd) || !currencies.includes(usdc)) {
    throw new Error(`missing expected currency options: ${JSON.stringify(currencies)}`);
  }
  const account = privateKeyToAccount(process.env.TEMPO_MPP_PAYER_PRIVATE_KEY as `0x${string}`);
  const client = createClient({ account, chain: Chain.testnet, transport: http(process.env.MPPX_RPC_URL) });
  await Actions.faucet.fundSync(client, { account, timeout: 60_000 });
  const payer = Mppx.create({
    methods: [tempo({ account, expectedChainId: 42431, getClient: () => client })],
    polyfill: false,
  });
  const paid = await payer.fetch(paidUrl, { headers: { accept: "application/json" } });
  if (!paid.ok) throw new Error(`pathUSD payment returned ${paid.status}`);
  const receiptHeader = paid.headers.get("payment-receipt");
  if (!receiptHeader) throw new Error("pathUSD response had no receipt");
  const receipt = Receipt.deserialize(receiptHeader);
  await paid.json();
  console.log(
    JSON.stringify({
      currencies,
      payer: account.address,
      paid: {
        hasReceipt: true,
        receiptReference: receipt.reference,
        status: paid.status,
      },
    }),
  );
}

main();
