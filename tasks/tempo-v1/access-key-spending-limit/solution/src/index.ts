import { writeFileSync } from "node:fs";
import { parseUnits, type Address } from "viem";
import { generatePrivateKey } from "viem/accounts";
import { Account, Actions, createClient, http } from "viem/tempo";
import { tempoTestnet } from "viem/tempo/chains";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

const token = required("TEMPO_TOKEN") as Address;
const recipient = required("TEMPO_RECIPIENT") as Address;
const decimals = Number(required("TEMPO_DECIMALS"));
const spendingLimit = parseUnits(required("TEMPO_SPENDING_LIMIT"), decimals);
const spendingPeriod = Number(required("TEMPO_SPENDING_PERIOD"));
const amount = parseUnits(required("TEMPO_AMOUNT"), decimals);
const overLimitAmount = parseUnits(required("TEMPO_OVER_LIMIT_AMOUNT"), decimals);
if (amount > spendingLimit) throw new Error("transfer amount exceeds spending limit");
if (!Number.isSafeInteger(spendingPeriod) || spendingPeriod < 0) {
  throw new Error("spending period must be a non-negative integer");
}

const payer = Account.fromSecp256k1(generatePrivateKey());
const accessKey = Account.fromSecp256k1(generatePrivateKey(), { access: payer });
const clientConfig = {
  chain: tempoTestnet,
  feeToken: token,
  transport: http(),
};
const payerClient = createClient({ ...clientConfig, account: payer });

await Actions.faucet.fundSync(payerClient, { account: payer.address });

const authorization = await Actions.accessKey.authorizeSync(payerClient, {
  accessKey,
  expiry: Math.floor(Date.now() / 1000) + 3600,
  limits: [{ token, limit: spendingLimit, period: spendingPeriod }],
});
if (authorization.receipt.status !== "success") throw new Error("access key authorization failed");

const accessKeyClient = createClient({ ...clientConfig, account: accessKey });
const transfer = await Actions.token.transferSync(accessKeyClient, {
  amount,
  to: recipient,
  token,
});
if (transfer.receipt.status !== "success") throw new Error("access key transfer failed");

const { remaining: remainingAfterTransfer } = await Actions.accessKey.getRemainingLimit(
  accessKeyClient,
  {
    account: payer.address,
    accessKey,
    token,
  },
);
if (overLimitAmount <= remainingAfterTransfer) {
  throw new Error("over-limit transfer amount must exceed the remaining limit");
}

const overLimitCall = Actions.token.transfer.call({
  amount: overLimitAmount,
  to: recipient,
  token,
});
const overLimitTransfer = await accessKeyClient.sendTransactionSync({
  calls: [overLimitCall],
  gas: 100_000n,
  throwOnReceiptRevert: false,
});
if (overLimitTransfer.status !== "reverted") {
  throw new Error("over-limit access key transfer did not revert");
}

const { remaining } = await Actions.accessKey.getRemainingLimit(accessKeyClient, {
  account: payer.address,
  accessKey,
  token,
});

const output = {
  payer: { address: payer.address },
  accessKey: { address: accessKey.accessKeyAddress },
  authorizationTransactionHash: authorization.receipt.transactionHash,
  transferTransactionHash: transfer.receipt.transactionHash,
  overLimitTransactionHash: overLimitTransfer.transactionHash,
  remainingLimit: remaining.toString(),
};
writeFileSync("/app/out.json", `${JSON.stringify(output, null, 2)}\n`);
console.log(JSON.stringify(output, null, 2));
