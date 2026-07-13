const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { privateKeyToAccount } = require("viem/accounts");
const { tempoTestnet } = require("viem/tempo/chains");

const walletId = "wallet-123";
const policyId = "policy-456";
const allowedRecipient = "0x2222222222222222222222222222222222222222";
const signer = privateKeyToAccount(`0x${"11".repeat(32)}`);

function loadCase(privyMock) {
  const privyPath = require.resolve("../src/privy");
  require.cache[privyPath] = { exports: privyMock };
  delete require.cache[require.resolve("../src/cases/privy-policy-enforcement")];
  return require("../src/cases/privy-policy-enforcement");
}

async function signedTransactionTo(to) {
  return signer.signTransaction({
    chainId: tempoTestnet.id,
    to,
    value: 1n,
    type: "eip1559",
    nonce: 0,
    gas: 21000n,
    maxFeePerGas: 1000000000n,
    maxPriorityFeePerGas: 1000000000n,
  });
}

async function writeResult() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  fs.writeFileSync(
    resultPath,
    JSON.stringify({
      wallet: { id: walletId, address: signer.address },
      policyId,
      signedTransaction: await signedTransactionTo(allowedRecipient),
    }),
  );
  return resultPath;
}

function privyMock(rpcResponses) {
  return {
    requirePrivyAuth() {},
    async getWallet() {
      return {
        id: walletId,
        address: signer.address,
        chain_type: "ethereum",
        policy_ids: [policyId],
      };
    },
    async getPolicy() {
      return { id: policyId, chain_type: "ethereum" };
    },
    async walletRpc(_config, _walletId, payload) {
      return rpcResponses(payload);
    },
  };
}

async function baseConfig() {
  return {
    resultPath: await writeResult(),
    privyAppId: "app",
    privyAppSecret: "secret",
    privyAllowedRecipient: allowedRecipient,
  };
}

test("replaces the configured recipient with a per-run recipient", () => {
  const { runtimeEnv } = loadCase({ requirePrivyAuth() {}, async getWallet() {} });
  const config = {
    privyAllowedRecipient: allowedRecipient,
  };

  const env = runtimeEnv(config);
  assert.match(env.PRIVY_ALLOWED_RECIPIENT, /^0x[0-9a-f]{40}$/);
  assert.equal(config.privyAllowedRecipient, env.PRIVY_ALLOWED_RECIPIENT);
  assert.notEqual(env.PRIVY_ALLOWED_RECIPIENT, allowedRecipient);
});

test("rejects a policy that does not deny a non-allowlisted recipient", async () => {
  const { verify } = loadCase(
    privyMock(async () => ({ status: 200, body: { data: { signed_transaction: "0x" } } })),
  );

  await assert.rejects(
    verify({ config: await baseConfig() }),
    /policy did not deny a non-allowlisted recipient/,
  );
});

test("rejects a policy that denies the allowed recipient", async () => {
  const { verify } = loadCase(
    privyMock(async () => ({
      status: 400,
      body: { error: "RPC request denied due to policy violation", code: "policy_violation" },
    })),
  );

  await assert.rejects(
    verify({ config: await baseConfig() }),
    /policy denied the allowed recipient/,
  );
});

test("accepts a policy that denies violations and allows the approved recipient", async () => {
  const { verify } = loadCase(
    privyMock(async (payload) => {
      const to = payload.params.transaction.to;
      if (to.toLowerCase() === allowedRecipient.toLowerCase()) {
        return {
          status: 200,
          body: { data: { signed_transaction: await signedTransactionTo(allowedRecipient) } },
        };
      }
      return {
        status: 400,
        body: { error: "RPC request denied due to policy violation", code: "policy_violation" },
      };
    }),
  );

  const evidence = await verify({ config: await baseConfig() });
  assert.equal(evidence.walletId, walletId);
  assert.equal(evidence.policyId, policyId);
  assert.equal(evidence.deniedProbeCount, 2);
});

test("rejects a 4xx denial that is not a policy violation", async () => {
  const { verify } = loadCase(
    privyMock(async (payload) => {
      const to = payload.params.transaction.to;
      if (to.toLowerCase() === allowedRecipient.toLowerCase()) {
        return {
          status: 200,
          body: { data: { signed_transaction: await signedTransactionTo(allowedRecipient) } },
        };
      }
      return { status: 400, body: { error: "invalid transaction" } };
    }),
  );

  await assert.rejects(
    verify({ config: await baseConfig() }),
    /policy did not deny a non-allowlisted recipient/,
  );
});
