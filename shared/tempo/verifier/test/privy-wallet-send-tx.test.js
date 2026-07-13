const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const walletId = "wallet-123";
const reportedAddress = "0x1111111111111111111111111111111111111111";
const actualAddress = "0x2222222222222222222222222222222222222222";
const transferHash = `0x${"02".repeat(32)}`;

function loadCase(privyMock) {
  const privyPath = require.resolve("../src/privy");
  require.cache[privyPath] = { exports: privyMock };
  delete require.cache[require.resolve("../src/cases/privy-wallet-send-tx")];
  return require("../src/cases/privy-wallet-send-tx");
}

function writeResult() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  fs.writeFileSync(
    resultPath,
    JSON.stringify({
      wallet: { id: walletId, address: reportedAddress },
      transferTransactionHash: transferHash,
    }),
  );
  return resultPath;
}

test("rejects a payer that is not the reported Privy wallet", async () => {
  const { verify } = loadCase({
    requirePrivyAuth() {},
    async getWallet() {
      return { id: walletId, address: actualAddress, chain_type: "ethereum" };
    },
  });
  const config = {
    resultPath: writeResult(),
    privyAppId: "app",
    privyAppSecret: "secret",
    amount: "0.21",
    decimals: 6,
    token: "0x4444444444444444444444444444444444444444",
    recipient: "0x3333333333333333333333333333333333333333",
  };

  await assert.rejects(
    verify({ client: {}, config, fromBlock: 1n }),
    /reported wallet address does not match the Privy wallet/,
  );
});
