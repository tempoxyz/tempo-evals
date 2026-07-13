const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const payer = "0x1111111111111111111111111111111111111111";
const token = "0x2222222222222222222222222222222222222222";
const salt = `0x${"01".repeat(32)}`;
const hash = (digit) => `0x${digit.repeat(64)}`;
const output = {
  payer: { address: payer },
  stablecoin: { address: token, name: "Agent Dollar", symbol: "AGD", salt },
  policy: { id: "1" },
  tokenCreateTransactionHash: hash("1"),
  policyCreateTransactionHash: hash("2"),
  policyAccountTransactionHash: hash("3"),
  linkPolicyTransactionHash: hash("4"),
};

const tempoPath = require.resolve("../src/tempo");
require.cache[tempoPath] = {
  exports: {
    findEvent(receipt, _address, event, matches) {
      const args = {
        TokenCreated: {
          token,
          name: "Agent Dollar",
          symbol: "AGD",
          currency: receipt.currency,
          admin: payer,
          salt,
        },
        PolicyCreated: {
          policyId: 1n,
          updater: payer,
          policyType: receipt.policyType === "whitelist" ? 0 : 1,
        },
        BlacklistUpdated: { policyId: 1n, updater: payer, account: payer, restricted: true },
        WhitelistUpdated: { policyId: 1n, updater: payer, account: payer, allowed: true },
        TransferPolicyUpdate: { updater: payer, newPolicyId: 1n },
      }[event.name];
      return matches(args) ? { args } : null;
    },
    receiptAfter: async (client) => ({
      blockNumber: 2n,
      currency: client.currency,
      policyType: client.policyType,
    }),
    sameAddress: (left, right) => left.toLowerCase() === right.toLowerCase(),
    waitForEvidence: async (_config, check) => check(),
  },
};
const { verify } = require("../src/cases/create-stablecoin-with-policy");

function fixture({
  accountAuthorized,
  currency = "USD",
  linkedPolicyId = 1n,
  policyType = "blacklist",
} = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  fs.writeFileSync(resultPath, JSON.stringify(output));

  return {
    client: {
      currency,
      policyType,
      readContract: async ({ functionName }) => {
        if (functionName === "transferPolicyId") return linkedPolicyId;
        if (functionName === "isAuthorized") {
          return accountAuthorized ?? policyType === "whitelist";
        }
        throw new Error(`unexpected contract read: ${functionName}`);
      },
    },
    config: {
      resultPath,
      stablecoinCurrency: "USD",
      policyType,
      policyAccount: payer,
      tip20Factory: payer,
      tip403Registry: payer,
    },
    fromBlock: 1n,
  };
}

test("rejects a stablecoin with the wrong configured currency", async () => {
  await assert.rejects(
    verify(fixture({ currency: "EUR" })),
    /does not create the output stablecoin/,
  );
});

test("rejects a policy that was linked and then unlinked", async () => {
  await assert.rejects(
    verify(fixture({ linkedPolicyId: 0n })),
    /stablecoin is not currently linked to the output policy/,
  );
});

test("rejects a blacklist account that was restricted and then unrestricted", async () => {
  await assert.rejects(
    verify(fixture({ accountAuthorized: true })),
    /account is not currently restricted by the output policy/,
  );
});

test("rejects a whitelist account that was allowed and then removed", async () => {
  await assert.rejects(
    verify(fixture({ accountAuthorized: false, policyType: "whitelist" })),
    /account is not currently allowed by the output policy/,
  );
});
