const { randomUUID } = require("node:crypto");
const { recoverMessageAddress } = require("viem");
const { expectAddress, expectObject, expectText, readResult } = require("../result");
const { getWallet, requirePrivyAuth } = require("../privy");
const { sameAddress } = require("../tempo");

function result(config) {
  return readResult(config, (value) => {
    expectObject(config, value, ["wallet", "signature"], "result");
    expectObject(config, value.wallet, ["id", "address"], "wallet");
    return {
      walletId: expectText(config, value.wallet.id, "wallet.id"),
      address: expectAddress(config, value.wallet.address, "wallet.address"),
      signature: expectText(config, value.signature, "signature"),
    };
  });
}

function signMessage(config) {
  if (!config.privyMessage) {
    throw new Error("missing required environment variable: PRIVY_MESSAGE");
  }
  return config.privySignMessage || config.privyMessage;
}

// Append a per-run nonce so a hard-coded signature can never satisfy the
// verifier. The submission receives the final message through PRIVY_MESSAGE.
function runtimeEnv(config) {
  config.privySignMessage = `${config.privyMessage} nonce=${randomUUID()}`;
  return { PRIVY_MESSAGE: config.privySignMessage };
}

async function verify({ config }) {
  requirePrivyAuth(config);
  const message = signMessage(config);
  const { walletId, address, signature } = result(config);

  const recovered = await recoverMessageAddress({ message, signature });
  if (!sameAddress(recovered, address)) {
    throw new Error("signature does not recover to the reported wallet address");
  }

  const wallet = await getWallet(config, walletId);
  if (!sameAddress(wallet.address, address)) {
    throw new Error("reported wallet address does not match the Privy wallet");
  }
  if (wallet.chain_type !== "ethereum") {
    throw new Error("Privy wallet is not an ethereum wallet");
  }

  return { walletId, address, message, recovered };
}

module.exports = { needsChain: false, runtimeEnv, verify };
