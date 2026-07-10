const { parseAbiItem } = require("viem");
const {
  expectAddress,
  expectHash,
  expectHex32,
  expectObject,
  expectText,
  expectUint,
  readResult,
} = require("../result");
const { defaultRuntimeEnv } = require("../submission");
const { findEvent, receiptAfter, sameAddress, waitForEvidence } = require("../tempo");

const POLICY_TYPES = { whitelist: 0, blacklist: 1 };
const TOKEN_CREATED = parseAbiItem(
  "event TokenCreated(address indexed token, string name, string symbol, string currency, address quoteToken, address admin, bytes32 salt)",
);
const POLICY_CREATED = parseAbiItem(
  "event PolicyCreated(uint64 indexed policyId, address indexed updater, uint8 policyType)",
);
const TRANSFER_POLICY_UPDATE = parseAbiItem(
  "event TransferPolicyUpdate(address indexed updater, uint64 indexed newPolicyId)",
);

function result(config) {
  return readResult(config, (value) => {
    expectObject(
      config,
      value,
      [
        "payer",
        "stablecoin",
        "policy",
        "tokenCreateTransactionHash",
        "policyCreateTransactionHash",
        "policyAccountTransactionHash",
        "linkPolicyTransactionHash",
      ],
      "result",
    );
    expectObject(config, value.payer, ["address"], "payer");
    expectObject(config, value.stablecoin, ["address", "name", "symbol", "currency", "salt"], "stablecoin");
    expectObject(config, value.policy, ["id"], "policy");
    return {
      payer: expectAddress(config, value.payer.address, "payer.address"),
      stablecoin: {
        address: expectAddress(config, value.stablecoin.address, "stablecoin.address"),
        name: expectText(config, value.stablecoin.name, "stablecoin.name"),
        symbol: expectText(config, value.stablecoin.symbol, "stablecoin.symbol"),
        currency: expectText(config, value.stablecoin.currency, "stablecoin.currency"),
        salt: expectHex32(config, value.stablecoin.salt, "stablecoin.salt"),
      },
      policyId: expectUint(config, value.policy.id, "policy.id"),
      tokenCreateTransactionHash: expectHash(config, value.tokenCreateTransactionHash, "tokenCreateTransactionHash"),
      policyCreateTransactionHash: expectHash(config, value.policyCreateTransactionHash, "policyCreateTransactionHash"),
      policyAccountTransactionHash: expectHash(config, value.policyAccountTransactionHash, "policyAccountTransactionHash"),
      linkPolicyTransactionHash: expectHash(config, value.linkPolicyTransactionHash, "linkPolicyTransactionHash"),
    };
  });
}

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_POLICY_ACCOUNT: config.policyAccount,
    TEMPO_POLICY_TYPE: config.policyType,
    TEMPO_STABLECOIN_CURRENCY: config.stablecoinCurrency,
  };
}

async function verify({ client, config, fromBlock }) {
  const output = result(config);
  const policyType = POLICY_TYPES[config.policyType];
  if (policyType === undefined) throw new Error(`unsupported policy type: ${config.policyType}`);
  const policyAccountEvent = parseAbiItem(
    config.policyType === "whitelist"
      ? "event WhitelistUpdated(uint64 indexed policyId, address indexed updater, address indexed account, bool allowed)"
      : "event BlacklistUpdated(uint64 indexed policyId, address indexed updater, address indexed account, bool restricted)",
  );

  return waitForEvidence(config, async () => {
    const tokenReceipt = await receiptAfter(
      client,
      fromBlock,
      output.tokenCreateTransactionHash,
      output.payer,
      "reported token-creation transaction",
    );
    const policyReceipt = await receiptAfter(
      client,
      fromBlock,
      output.policyCreateTransactionHash,
      output.payer,
      "reported policy-creation transaction",
    );
    const accountReceipt = await receiptAfter(
      client,
      fromBlock,
      output.policyAccountTransactionHash,
      output.payer,
      "reported policy-account transaction",
    );
    const linkReceipt = await receiptAfter(
      client,
      fromBlock,
      output.linkPolicyTransactionHash,
      output.payer,
      "reported policy-link transaction",
    );
    if (!tokenReceipt || !policyReceipt || !accountReceipt || !linkReceipt) return null;

    const token = findEvent(tokenReceipt, config.tip20Factory, TOKEN_CREATED, (args) =>
      sameAddress(args.token, output.stablecoin.address) &&
      args.name === output.stablecoin.name &&
      args.symbol === output.stablecoin.symbol &&
      args.currency === output.stablecoin.currency &&
      args.currency === config.stablecoinCurrency &&
      sameAddress(args.admin, output.payer) &&
      args.salt.toLowerCase() === output.stablecoin.salt.toLowerCase(),
    );
    if (!token) throw new Error("reported token-creation transaction does not create the output stablecoin");

    const policy = findEvent(policyReceipt, config.tip403Registry, POLICY_CREATED, (args) =>
      args.policyId.toString() === output.policyId &&
      sameAddress(args.updater, output.payer) &&
      Number(args.policyType) === policyType,
    );
    if (!policy) throw new Error("reported policy-creation transaction does not create the output policy");

    const policyAccount = findEvent(accountReceipt, config.tip403Registry, policyAccountEvent, (args) =>
      args.policyId.toString() === output.policyId &&
      sameAddress(args.updater, output.payer) &&
      sameAddress(args.account, config.policyAccount) &&
      (config.policyType === "whitelist" ? args.allowed : args.restricted),
    );
    if (!policyAccount) throw new Error("reported policy-account transaction does not update the required account");

    const link = findEvent(linkReceipt, output.stablecoin.address, TRANSFER_POLICY_UPDATE, (args) =>
      sameAddress(args.updater, output.payer) && args.newPolicyId.toString() === output.policyId,
    );
    if (!link) throw new Error("reported policy-link transaction does not link the output policy");

    return {
      blockNumber: linkReceipt.blockNumber.toString(),
      payer: output.payer,
      token: output.stablecoin.address,
      policyId: output.policyId,
    };
  }, "stablecoin policy flow was not observed");
}

module.exports = { runtimeEnv, verify };
