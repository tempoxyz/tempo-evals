const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const walletId = "wallet-123";
const reportedAddress = "0x1111111111111111111111111111111111111111";
const actualAddress = "0x2222222222222222222222222222222222222222";

function loadCase(privyMock) {
  const privyPath = require.resolve("../src/privy");
  require.cache[privyPath] = { exports: privyMock };
  delete require.cache[require.resolve("../src/cases/privy-wallet-create")];
  return require("../src/cases/privy-wallet-create");
}

function writeResult(wallet) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  fs.writeFileSync(resultPath, JSON.stringify({ wallet }));
  return resultPath;
}

const config = (resultPath) => ({
  resultPath,
  privyApiUrl: "https://api.privy.example",
  privyAppId: "app",
  privyAppSecret: "secret",
});

test("rejects a reported wallet whose address does not match Privy", async () => {
  const { verify } = loadCase({
    requirePrivyAuth() {},
    async getWallet() {
      return { id: walletId, address: actualAddress, chain_type: "ethereum", created_at: Date.now() };
    },
  });
  const resultPath = writeResult({ id: walletId, address: reportedAddress, chainType: "ethereum" });

  await assert.rejects(
    verify({ config: config(resultPath), startedAt: Date.now() }),
    /reported wallet address does not match the Privy wallet/,
  );
});

test("rejects a wallet created before this evaluation", async () => {
  const { verify } = loadCase({
    requirePrivyAuth() {},
    async getWallet() {
      return {
        id: walletId,
        address: reportedAddress,
        chain_type: "ethereum",
        created_at: Date.now() - 3600000,
      };
    },
  });
  const resultPath = writeResult({ id: walletId, address: reportedAddress, chainType: "ethereum" });

  await assert.rejects(
    verify({ config: config(resultPath), startedAt: Date.now() }),
    /reported wallet predates this evaluation/,
  );
});

test("accepts a fresh matching wallet", async () => {
  const { verify } = loadCase({
    requirePrivyAuth() {},
    async getWallet() {
      return { id: walletId, address: reportedAddress, chain_type: "ethereum", created_at: Date.now() };
    },
  });
  const resultPath = writeResult({ id: walletId, address: reportedAddress, chainType: "ethereum" });

  const evidence = await verify({ config: config(resultPath), startedAt: Date.now() });
  assert.equal(evidence.walletId, walletId);
  assert.equal(evidence.address, reportedAddress);
});
