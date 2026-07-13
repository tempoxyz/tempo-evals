// SYNCED FROM shared/tempo/verifier/src/tempo.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
const { createPublicClient, decodeEventLog, http, pad, stringToHex } = require("viem");
const { tempoTestnet } = require("viem/tempo/chains");

function createTempoClient() {
  return createPublicClient({ chain: tempoTestnet, transport: http() });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForEvidence(config, check, failureMessage) {
  const deadline = Date.now() + config.logWaitMs;

  while (Date.now() < deadline) {
    const evidence = await check();
    if (evidence) return evidence;
    await sleep(1000);
  }

  throw new Error(failureMessage);
}

function blockEvidence(log, extra = {}) {
  return {
    transactionHash: log.transactionHash,
    blockNumber: log.blockNumber?.toString(),
    ...extra,
  };
}

function sameAddress(left, right) {
  return left?.toLowerCase() === right?.toLowerCase();
}

function findEvent(receipt, address, event, matches) {
  for (const log of receipt.logs) {
    if (!sameAddress(log.address, address)) continue;
    try {
      const decoded = decodeEventLog({ abi: [event], data: log.data, topics: log.topics });
      if (matches(decoded.args)) return decoded;
    } catch {
      // Ignore unrelated logs.
    }
  }
  return null;
}

async function receiptAfter(client, fromBlock, hash, from, label) {
  let receipt;
  try {
    receipt = await client.getTransactionReceipt({ hash });
  } catch {
    return null;
  }
  if (receipt.status !== "success") throw new Error(`${label} did not succeed`);
  if (receipt.blockNumber <= fromBlock) throw new Error(`${label} predates this evaluation`);
  if (from && !sameAddress(receipt.from, from)) {
    throw new Error(`${label} was not sent by the reported account`);
  }
  return receipt;
}

async function waitForRpc(client, config) {
  const deadline = Date.now() + config.rpcWaitMs;
  while (Date.now() < deadline) {
    try {
      return await client.getBlockNumber();
    } catch {
      await sleep(1000);
    }
  }
  throw new Error("Tempo testnet RPC was not reachable");
}

function memoEncodings(memo) {
  return Array.from(
    new Set([
      pad(stringToHex(memo), { size: 32, dir: "left" }),
      pad(stringToHex(memo), { size: 32, dir: "right" }),
      stringToHex(memo, { size: 32 }),
    ]),
  );
}

module.exports = {
  blockEvidence,
  createTempoClient,
  findEvent,
  memoEncodings,
  receiptAfter,
  sameAddress,
  sleep,
  waitForEvidence,
  waitForRpc,
};
