const { randomBytes } = require("node:crypto");
const { parseTransaction, recoverTransactionAddress } = require("viem");
const { tempoTestnet } = require("viem/tempo/chains");
const { expectAddress, expectObject, expectText, readResult } = require("../result");
const { getPolicy, getWallet, requirePrivyAuth, walletRpc } = require("../privy");
const { sameAddress } = require("../tempo");

function result(config) {
  return readResult(config, (value) => {
    expectObject(config, value, ["wallet", "policyId", "signedTransaction"], "result");
    expectObject(config, value.wallet, ["id", "address"], "wallet");
    return {
      walletId: expectText(config, value.wallet.id, "wallet.id"),
      address: expectAddress(config, value.wallet.address, "wallet.address"),
      policyId: expectText(config, value.policyId, "policyId"),
      signedTransaction: expectText(config, value.signedTransaction, "signedTransaction"),
    };
  });
}

function allowedRecipient(config) {
  if (!config.privyAllowedRecipient) {
    throw new Error("missing required environment variable: PRIVY_ALLOWED_RECIPIENT");
  }
  return config.privyAllowedRecipient;
}

function randomRecipient(config) {
  const allowed = allowedRecipient(config).toLowerCase();
  for (;;) {
    const candidate = `0x${randomBytes(20).toString("hex")}`;
    if (candidate !== allowed) return candidate;
  }
}

function randomAllowedRecipient() {
  return `0x${randomBytes(20).toString("hex")}`;
}

function signTransactionProbe(to) {
  return {
    method: "eth_signTransaction",
    chain_type: "ethereum",
    params: {
      transaction: {
        to,
        value: "0x1",
        chain_id: tempoTestnet.id,
        type: 2,
        nonce: 0,
        gas_limit: "0x5208",
        max_fee_per_gas: "0x3b9aca00",
        max_priority_fee_per_gas: "0x3b9aca00",
      },
    },
  };
}

async function checkSignedTransaction(config, serializedTransaction, address) {
  const allowed = allowedRecipient(config);
  const transaction = parseTransaction(serializedTransaction);
  if (!sameAddress(transaction.to, allowed)) {
    throw new Error("reported signed transaction is not addressed to the allowed recipient");
  }
  const signer = await recoverTransactionAddress({ serializedTransaction });
  if (!sameAddress(signer, address)) {
    throw new Error("reported signed transaction was not signed by the Privy wallet");
  }
}

function runtimeEnv(config) {
  config.privyAllowedRecipient = randomAllowedRecipient();
  return { PRIVY_ALLOWED_RECIPIENT: config.privyAllowedRecipient };
}

async function verify({ config }) {
  requirePrivyAuth(config);
  const allowed = allowedRecipient(config);
  const { walletId, address, policyId, signedTransaction } = result(config);

  const wallet = await getWallet(config, walletId);
  if (!sameAddress(wallet.address, address)) {
    throw new Error("reported wallet address does not match the Privy wallet");
  }
  if (wallet.chain_type !== "ethereum") {
    throw new Error("Privy wallet is not an ethereum wallet");
  }
  if (!Array.isArray(wallet.policy_ids) || !wallet.policy_ids.includes(policyId)) {
    throw new Error("reported policy is not attached to the Privy wallet");
  }

  const policy = await getPolicy(config, policyId);
  if (policy.chain_type !== "ethereum") {
    throw new Error("Privy policy is not an ethereum policy");
  }

  await checkSignedTransaction(config, signedTransaction, address);

  // Independently probe the live policy: a non-allowlisted recipient must be
  // denied, and the allowed recipient must be signable. Privy reports policy
  // denials as a 4xx response with code "policy_violation".
  for (let index = 0; index < 2; index += 1) {
    const denied = await walletRpc(
      config,
      walletId,
      signTransactionProbe(randomRecipient(config)),
    );
    const deniedByPolicy =
      denied.status >= 400 &&
      denied.status < 500 &&
      denied.body?.code === "policy_violation";
    if (!deniedByPolicy) {
      throw new Error(
        `policy did not deny a non-allowlisted recipient (status ${denied.status})`,
      );
    }
  }

  const compliant = await walletRpc(config, walletId, signTransactionProbe(allowed));
  if (compliant.status !== 200) {
    throw new Error(
      `policy denied the allowed recipient (status ${compliant.status})`,
    );
  }
  const compliantSigned = compliant.body?.data?.signed_transaction;
  if (typeof compliantSigned !== "string" || !compliantSigned) {
    throw new Error("compliant signing probe did not return a signed transaction");
  }
  await checkSignedTransaction(config, compliantSigned, address);

  return {
    walletId,
    address,
    policyId,
    allowedRecipient: allowed,
    deniedProbeCount: 2,
  };
}

module.exports = { needsChain: false, runtimeEnv, verify };
