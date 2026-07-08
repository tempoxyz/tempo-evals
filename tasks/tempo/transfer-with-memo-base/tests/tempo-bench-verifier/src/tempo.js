// AUTO-GENERATED FROM shared/verifier/src/tempo.js BY npm run sync. DO NOT EDIT MANUALLY.
const { createPublicClient, http, pad, stringToHex } = require("viem");

function createTempoClient(config) {
  return createPublicClient({ transport: http(config.rpcUrl) });
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

async function waitForRpc(client, config) {
  const deadline = Date.now() + config.rpcWaitMs;
  while (Date.now() < deadline) {
    try {
      return await client.getBlockNumber();
    } catch {
      await sleep(1000);
    }
  }
  throw new Error(`Tempo RPC was not reachable at ${config.rpcUrl}`);
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
  memoEncodings,
  sameAddress,
  sleep,
  waitForEvidence,
  waitForRpc,
};
