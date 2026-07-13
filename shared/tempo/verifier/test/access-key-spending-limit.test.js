const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { encodeFunctionData, parseAbiItem, parseUnits, toFunctionSelector } = require("viem");

const payer = "0x1111111111111111111111111111111111111111";
const accessKey = "0x2222222222222222222222222222222222222222";
const recipient = "0x3333333333333333333333333333333333333333";
const token = "0x4444444444444444444444444444444444444444";
const accountKeychain = "0xaaaaaaAA00000000000000000000000000000000";
const authorizationHash = `0x${"01".repeat(32)}`;
const transferHash = `0x${"02".repeat(32)}`;
const overLimitHash = `0x${"03".repeat(32)}`;
const transferFunction = parseAbiItem("function transfer(address to, uint256 amount) returns (bool)");

test("requires exact limit authorization and a SpendingLimitExceeded onchain rejection", async () => {
  const limit = parseUnits("0.50", 6);
  const amount = parseUnits("0.21", 6);
  const overLimitAmount = parseUnits("0.50", 6);
  const postTransferRemaining = parseUnits("0.28", 6);
  const finalRemaining = parseUnits("0.27", 6);
  let authorizedLimit = limit;
  let traceReturnValue = toFunctionSelector("SpendingLimitExceeded()");

  const viemTempoPath = require.resolve("viem/tempo");
  require.cache[viemTempoPath] = {
    exports: {
      Addresses: { accountKeychain },
      Actions: {
        accessKey: {
          getMetadata: async () => ({ spendPolicy: "limited", isRevoked: false }),
          getRemainingLimit: async (_client, parameters) => ({
            remaining: parameters.blockNumber === 2n
              ? limit
              : parameters.blockNumber === 3n
                ? postTransferRemaining
                : finalRemaining,
          }),
        },
      },
    },
  };
  const tempoPath = require.resolve("../src/tempo");
  require.cache[tempoPath] = {
    exports: {
      findEvent(receipt, address, event, matches) {
        const args = receipt.kind === "over-limit" && event.name === "Transfer"
          ? { from: payer, to: payer, value: 1n }
          : {
              KeyAuthorized: {
                account: payer,
                publicKey: accessKey,
                signatureType: 0,
                expiry: 1n,
              },
              Transfer: { from: payer, to: recipient, value: amount },
              AccessKeySpend: {
                account: payer,
                publicKey: accessKey,
                token,
                amount,
                remainingLimit: postTransferRemaining,
              },
            }[event.name];
        const expectedAddress = event.name === "Transfer" ? token : accountKeychain;
        return address.toLowerCase() === expectedAddress.toLowerCase() && matches(args)
          ? { args }
          : null;
      },
      receiptAfter: async (_client, _fromBlock, hash) =>
        hash === authorizationHash
          ? { blockNumber: 2n, transactionIndex: 0, kind: "authorization" }
          : { blockNumber: 3n, transactionIndex: 0, kind: "transfer" },
      sameAddress: (left, right) => left?.toLowerCase() === right?.toLowerCase(),
      waitForEvidence: async (_config, check) => check(),
    },
  };
  delete require.cache[require.resolve("../src/cases/access-key-spending-limit")];
  const { verify } = require("../src/cases/access-key-spending-limit");

  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  fs.writeFileSync(
    resultPath,
    JSON.stringify({
      payer: { address: payer },
      accessKey: { address: accessKey },
      authorizationTransactionHash: authorizationHash,
      transferTransactionHash: transferHash,
      overLimitTransactionHash: overLimitHash,
      remainingLimit: finalRemaining.toString(),
    }),
  );
  const accessKeySignature = {
    type: "keychain",
    userAddress: payer,
    keyId: accessKey,
  };
  const input = {
    client: {
      getTransaction: async ({ hash }) => {
        if (hash === authorizationHash) {
          return {
            type: "tempo",
            typeHex: "0x76",
            keyAuthorization: {
              address: accessKey,
              limits: [{ token, limit: authorizedLimit, period: 0 }],
            },
          };
        }
        if (hash === overLimitHash) {
          return {
            type: "tempo",
            typeHex: "0x76",
            signature: accessKeySignature,
            calls: [{
              to: token,
              data: encodeFunctionData({
                abi: [transferFunction],
                functionName: "transfer",
                args: [recipient, overLimitAmount],
              }),
            }],
          };
        }
        return { type: "tempo", typeHex: "0x76", signature: accessKeySignature };
      },
      getTransactionReceipt: async () => ({
        status: "reverted",
        blockNumber: 4n,
        transactionIndex: 0,
        from: payer,
        kind: "over-limit",
      }),
      request: async () => ({ failed: true, returnValue: traceReturnValue }),
    },
    config: {
      resultPath,
      amount: "0.21",
      spendingLimit: "0.50",
      spendingPeriod: "0",
      overLimitAmount: "0.50",
      decimals: 6,
      token,
      recipient,
    },
    fromBlock: 1n,
  };

  const evidence = await verify(input);
  assert.equal(evidence.overLimitAmount, overLimitAmount.toString());

  authorizedLimit = limit - 1n;
  await assert.rejects(
    verify(input),
    /reported authorization transaction does not contain the configured limit/,
  );

  authorizedLimit = limit;
  traceReturnValue = "0xdeadbeef";
  await assert.rejects(
    verify(input),
    /did not revert with SpendingLimitExceeded/,
  );
});
