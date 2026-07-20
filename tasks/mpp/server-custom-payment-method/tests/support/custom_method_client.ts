import { createRequire } from "node:module";

async function main() {
  const require = createRequire("/opt/stable-bench/verifier/package.json");
  const { Challenge, Credential, Receipt } = await import(require.resolve("mppx"));

  const paidUrl = process.env.TEMPO_MPP_PAID_URL;
  const accessKey = process.env.MPP_CUSTOM_ACCESS_KEY;

  const offer = await fetch(paidUrl, {
    headers: { accept: "application/json" },
  });
  const challenge = Challenge.fromResponse(offer);

  const wrongCredential = Credential.serialize({
    challenge,
    payload: { accessKey: "wrong-access-key" },
  });
  const wrong = await fetch(paidUrl, {
    headers: {
      accept: "application/json",
      authorization: wrongCredential,
    },
  });

  const credential = Credential.serialize({
    challenge,
    payload: { accessKey },
  });
  const paid = await fetch(paidUrl, {
    headers: {
      accept: "application/json",
      authorization: credential,
    },
  });
  const receiptHeader = paid.headers.get("payment-receipt");
  const receipt = receiptHeader ? Receipt.deserialize(receiptHeader) : null;
  await paid.json();

  console.log(
    JSON.stringify({
      offer: {
        status: offer.status,
        method: challenge.method,
        intent: challenge.intent,
        resource: challenge.request.resource,
      },
      wrong: {
        status: wrong.status,
        rejected: wrong.status >= 400,
      },
      paid: {
        status: paid.status,
        json: true,
        hasReceipt: Boolean(receiptHeader),
        receipt,
      },
    }),
  );
}

main();
