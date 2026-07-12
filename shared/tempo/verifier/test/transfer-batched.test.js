const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const {
  encodeAbiParameters,
  encodeEventTopics,
  encodeFunctionData,
  parseAbi,
  parseAbiItem,
  parseUnits,
} = require("viem");

const { verify } = require("../src/cases/transfer-batched");

const payer = "0x1111111111111111111111111111111111111111";
const recipient = "0x2222222222222222222222222222222222222222";
const redirect = "0x3333333333333333333333333333333333333333";
const token = "0x4444444444444444444444444444444444444444";
const transactionHash = `0x${"01".repeat(32)}`;
const amount = parseUnits("0.01", 6);
const transferAbi = parseAbi(["function transfer(address to, uint256 value)"]);
const transferEvent = parseAbiItem("event Transfer(address indexed from, address indexed to, uint256 value)");

function transferLog(to) {
  return {
    address: token,
    data: encodeAbiParameters([{ type: "uint256" }], [amount]),
    topics: encodeEventTopics({ abi: [transferEvent], eventName: "Transfer", args: { from: payer, to } }),
  };
}

function fixture(deliveredTo) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-"));
  const resultPath = path.join(dir, "out.json");
  fs.writeFileSync(
    resultPath,
    JSON.stringify({ payer: { address: payer }, transferTransactionHash: transactionHash }),
  );
  return {
    client: {
      getTransaction: async () => ({
        calls: [
          {
            data: encodeFunctionData({
              abi: transferAbi,
              functionName: "transfer",
              args: [recipient, amount],
            }),
            to: token,
          },
        ],
      }),
      getTransactionReceipt: async () => ({
        blockNumber: 2n,
        from: payer,
        logs: [transferLog(deliveredTo)],
        status: "success",
      }),
    },
    config: {
      amount: "0.01",
      decimals: 6,
      logWaitMs: 10,
      recipients: [recipient],
      resultPath,
      token,
    },
    fromBlock: 1n,
  };
}

test("accepts a requested batch payment delivered to the recipient", async () => {
  const evidence = await verify(fixture(recipient));

  assert.deepEqual(evidence.recipients, [recipient]);
});

test("rejects a requested batch payment redirected by a receive policy", async () => {
  await assert.rejects(
    verify(fixture(redirect)),
    /did not deliver payment to every configured recipient/,
  );
});
