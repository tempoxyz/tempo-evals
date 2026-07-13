const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { privateKeyToAccount } = require("viem/accounts");

const walletId = "wallet-123";
const signer = privateKeyToAccount(`0x${"11".repeat(32)}`);
const otherAddress = "0x2222222222222222222222222222222222222222";

function loadCase(privyMock) {
  const privyPath = require.resolve("../src/privy");
  require.cache[privyPath] = { exports: privyMock };
  delete require.cache[require.resolve("../src/cases/privy-wallet-sign")];
  return require("../src/cases/privy-wallet-sign");
}

function writeResult(result) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  fs.writeFileSync(resultPath, JSON.stringify(result));
  return resultPath;
}

function baseConfig(resultPath) {
  return {
    resultPath,
    privyApiUrl: "https://api.privy.example",
    privyAppId: "app",
    privyAppSecret: "secret",
    privyMessage: "Tempo Privy bench signing check",
  };
}

test("appends a per-run nonce to the runtime message", () => {
  const { runtimeEnv } = loadCase({ requirePrivyAuth() {}, async getWallet() {} });
  const config = baseConfig("/tmp/unused");
  const env = runtimeEnv(config);
  assert.match(env.PRIVY_MESSAGE, /^Tempo Privy bench signing check nonce=/);
  assert.equal(config.privySignMessage, env.PRIVY_MESSAGE);
});

test("rejects a signature that does not recover to the reported address", async () => {
  const { runtimeEnv, verify } = loadCase({
    requirePrivyAuth() {},
    async getWallet() {
      return { id: walletId, address: otherAddress, chain_type: "ethereum" };
    },
  });
  const config = baseConfig("/tmp/unused");
  const env = runtimeEnv(config);
  const signature = await signer.signMessage({ message: env.PRIVY_MESSAGE });
  config.resultPath = writeResult({
    wallet: { id: walletId, address: otherAddress },
    signature,
  });

  await assert.rejects(
    verify({ config }),
    /signature does not recover to the reported wallet address/,
  );
});

test("accepts a valid signature over the nonced message", async () => {
  const { runtimeEnv, verify } = loadCase({
    requirePrivyAuth() {},
    async getWallet() {
      return { id: walletId, address: signer.address, chain_type: "ethereum" };
    },
  });
  const config = baseConfig("/tmp/unused");
  const env = runtimeEnv(config);
  const signature = await signer.signMessage({ message: env.PRIVY_MESSAGE });
  config.resultPath = writeResult({
    wallet: { id: walletId, address: signer.address },
    signature,
  });

  const evidence = await verify({ config });
  assert.equal(evidence.walletId, walletId);
  assert.equal(evidence.recovered.toLowerCase(), signer.address.toLowerCase());
});
