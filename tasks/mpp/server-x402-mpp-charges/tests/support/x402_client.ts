import { createRequire } from "node:module";

async function main() {
  const workspace = process.env.TEMPO_BENCH_WORKSPACE ?? "/app";
  const require = createRequire(`${workspace}/package.json`);
  const { Mppx, evm } = await import(require.resolve("mppx/client"));
  const { x402 } = await import(require.resolve("mppx"));
  const { generatePrivateKey, privateKeyToAccount } = await import(
    require.resolve("viem/accounts"),
  );
  const url = process.env.TEMPO_MPP_X402_PAID_URL!;
  const account = privateKeyToAccount(generatePrivateKey());
  const client = Mppx.create({
    methods: [
      evm.charge({
        account,
        currencies: [evm.assets.baseSepolia.USDC],
        maxAmount: "0.01",
        networks: [84532],
      }),
    ],
    polyfill: false,
  });

  const required = await client.rawFetch(url, { headers: { accept: "application/json" } });
  if (required.status !== 402) throw new Error(`expected 402, received ${required.status}`);
  const requiredHeader = required.headers.get("payment-required");
  if (!requiredHeader) throw new Error("missing PAYMENT-REQUIRED header");
  const offer = x402.Header.decodePaymentRequired(requiredHeader);
  const accepted = offer.accepts.find(
    (value) =>
      value.scheme === "exact" &&
      value.network === "eip155:84532" &&
      value.asset.toLowerCase() === evm.assets.baseSepolia.USDC.address.toLowerCase(),
  );
  if (!accepted) throw new Error("x402 offer did not include Base Sepolia USDC exact payment");

  const credential = await client.createCredential(
    new Response(null, {
      headers: { "payment-required": requiredHeader },
      status: 402,
    }),
  );
  const paid = await client.rawFetch(url, {
    headers: { "payment-signature": credential },
  });
  if (!paid.ok) throw new Error(`x402 payment returned ${paid.status}`);
  await paid.json();
  const receipt = paid.headers.get("payment-receipt");
  const paymentResponse = paid.headers.get("payment-response");
  if (!receipt) throw new Error("x402 response did not include Payment-Receipt");
  if (!paymentResponse) throw new Error("x402 response did not include PAYMENT-RESPONSE");
  const settlement = x402.Header.decodePaymentResponse(paymentResponse);
  if (!settlement.success) throw new Error("x402 settlement did not succeed");

  console.log(
    JSON.stringify({
      offer: { asset: accepted.asset, network: accepted.network, scheme: accepted.scheme },
      paid: { hasReceipt: true, hasSettlement: true, status: paid.status },
    }),
  );
}

main();
