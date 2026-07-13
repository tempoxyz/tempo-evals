const { expectAddress, expectObject, expectText, readResult } = require("../result");
const { getWallet, requirePrivyAuth } = require("../privy");
const { sameAddress } = require("../tempo");

// Allow modest clock skew between the verifier host and the Privy API.
const CREATED_AT_SLACK_MS = 60000;

function result(config) {
  return readResult(config, (value) => {
    expectObject(config, value, ["wallet"], "result");
    expectObject(config, value.wallet, ["id", "address", "chainType"], "wallet");
    if (value.wallet.chainType !== "ethereum") {
      throw new Error("wallet.chainType must be \"ethereum\"");
    }
    return {
      walletId: expectText(config, value.wallet.id, "wallet.id"),
      address: expectAddress(config, value.wallet.address, "wallet.address"),
    };
  });
}

function runtimeEnv() {
  return {};
}

async function verify({ config, startedAt }) {
  requirePrivyAuth(config);
  const { walletId, address } = result(config);

  const wallet = await getWallet(config, walletId);
  if (!sameAddress(wallet.address, address)) {
    throw new Error("reported wallet address does not match the Privy wallet");
  }
  if (wallet.chain_type !== "ethereum") {
    throw new Error("Privy wallet is not an ethereum wallet");
  }
  if (
    startedAt &&
    typeof wallet.created_at === "number" &&
    wallet.created_at < startedAt - CREATED_AT_SLACK_MS
  ) {
    throw new Error("reported wallet predates this evaluation");
  }

  return {
    walletId,
    address,
    createdAt: wallet.created_at ?? null,
  };
}

module.exports = { needsChain: false, runtimeEnv, verify };
