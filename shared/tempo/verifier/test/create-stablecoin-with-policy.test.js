const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const payer = "0x1111111111111111111111111111111111111111";
const token = "0x2222222222222222222222222222222222222222";
const salt = `0x${"01".repeat(32)}`;
const hash = (digit) => `0x${digit.repeat(64)}`;

test("rejects a stablecoin with the wrong configured currency", async () => {
  const tempoPath = require.resolve("../src/tempo");
  require.cache[tempoPath] = {
    exports: {
      findEvent(_receipt, _address, event, matches) {
        const args = {
          TokenCreated: { token, name: "Agent Dollar", symbol: "AGD", currency: "EUR", admin: payer, salt },
          PolicyCreated: { policyId: 1n, updater: payer, policyType: 1 },
          BlacklistUpdated: { policyId: 1n, updater: payer, account: payer, restricted: true },
          TransferPolicyUpdate: { updater: payer, newPolicyId: 1n },
        }[event.name];
        return matches(args) ? { args } : null;
      },
      receiptAfter: async () => ({ blockNumber: 2n }),
      sameAddress: (left, right) => left.toLowerCase() === right.toLowerCase(),
      waitForEvidence: async (_config, check) => check(),
    },
  };
  delete require.cache[require.resolve("../src/cases/create-stablecoin-with-policy")];
  const { verify } = require("../src/cases/create-stablecoin-with-policy");

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  fs.writeFileSync(
    resultPath,
    JSON.stringify({
      payer: { address: payer },
      stablecoin: { address: token, name: "Agent Dollar", symbol: "AGD", salt },
      policy: { id: "1" },
      tokenCreateTransactionHash: hash("1"),
      policyCreateTransactionHash: hash("2"),
      policyAccountTransactionHash: hash("3"),
      linkPolicyTransactionHash: hash("4"),
    }),
  );

  await assert.rejects(
    verify({
      client: {},
      config: {
        resultPath,
        stablecoinCurrency: "USD",
        policyType: "blacklist",
        policyAccount: payer,
        tip20Factory: payer,
        tip403Registry: payer,
      },
      fromBlock: 1n,
    }),
    /does not create the output stablecoin/,
  );
});
