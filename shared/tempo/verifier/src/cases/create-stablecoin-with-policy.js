// SYNCED FROM shared/tempo/verifier/src/cases/create-stablecoin-with-policy.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
const { parseAbiItem } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { sameAddress, waitForEvidence } = require("../tempo");

const POLICY_TYPES = {
  whitelist: 0,
  blacklist: 1,
};

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_TIP20_FACTORY: config.tip20Factory,
    TEMPO_TIP403_REGISTRY: config.tip403Registry,
    TEMPO_STABLECOIN_NAME: config.stablecoinName,
    TEMPO_STABLECOIN_SYMBOL: config.stablecoinSymbol,
    TEMPO_STABLECOIN_CURRENCY: config.stablecoinCurrency,
    TEMPO_STABLECOIN_SALT: config.stablecoinSalt,
    TEMPO_POLICY_TYPE: config.policyType,
    TEMPO_POLICY_ACCOUNT: config.policyAccount,
  };
}

function beforeLog(left, right) {
  return (
    left.blockNumber < right.blockNumber ||
    (left.blockNumber === right.blockNumber && left.logIndex < right.logIndex)
  );
}

function sameHex(left, right) {
  return left?.toLowerCase() === right?.toLowerCase();
}

async function verify({ client, config, fromBlock }) {
  const admin = privateKeyToAccount(config.payerPrivateKey).address;
  const expectedPolicyType = POLICY_TYPES[config.policyType];
  if (expectedPolicyType === undefined) {
    throw new Error(`unsupported policy type: ${config.policyType}`);
  }

  const tokenCreated = parseAbiItem(
    "event TokenCreated(address indexed token, string name, string symbol, string currency, address quoteToken, address admin, bytes32 salt)",
  );
  const policyCreated = parseAbiItem(
    "event PolicyCreated(uint64 indexed policyId, address indexed updater, uint8 policyType)",
  );
  const transferPolicyUpdate = parseAbiItem(
    "event TransferPolicyUpdate(address indexed updater, uint64 indexed newPolicyId)",
  );
  const policyAccountUpdated = parseAbiItem(
    config.policyType === "whitelist"
      ? "event WhitelistUpdated(uint64 indexed policyId, address indexed updater, address indexed account, bool allowed)"
      : "event BlacklistUpdated(uint64 indexed policyId, address indexed updater, address indexed account, bool restricted)",
  );

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const tokenLogs = await client.getLogs({
      address: config.tip20Factory,
      event: tokenCreated,
      fromBlock,
      toBlock: latestBlock,
    });
    const tokenLog = tokenLogs.find(
      (log) =>
        log.args.name === config.stablecoinName &&
        log.args.symbol === config.stablecoinSymbol &&
        log.args.currency === config.stablecoinCurrency &&
        sameAddress(log.args.admin, admin) &&
        sameHex(log.args.salt, config.stablecoinSalt),
    );

    if (!tokenLog) {
      return null;
    }

    const policyLogs = await client.getLogs({
      address: config.tip403Registry,
      event: policyCreated,
      args: { updater: admin },
      fromBlock,
      toBlock: latestBlock,
    });
    const policyLog = policyLogs.find((log) => Number(log.args.policyType) === expectedPolicyType);
    if (!policyLog) {
      return null;
    }

    const policyAccountLogs = await client.getLogs({
      address: config.tip403Registry,
      event: policyAccountUpdated,
      args: {
        policyId: policyLog.args.policyId,
        updater: admin,
        account: config.policyAccount,
      },
      fromBlock,
      toBlock: latestBlock,
    });
    const policyAccountLog = policyAccountLogs.find((log) =>
      config.policyType === "whitelist" ? log.args.allowed : log.args.restricted,
    );
    if (!policyAccountLog) {
      return null;
    }

    const linkLogs = await client.getLogs({
      address: tokenLog.args.token,
      event: transferPolicyUpdate,
      args: {
        updater: admin,
        newPolicyId: policyLog.args.policyId,
      },
      fromBlock,
      toBlock: latestBlock,
    });
    const linkLog = linkLogs.find(
      (log) =>
        beforeLog(tokenLog, log) &&
        beforeLog(policyLog, log) &&
        beforeLog(policyAccountLog, log),
    );
    if (linkLog) {
      return {
        token: tokenLog.args.token,
        policyId: policyLog.args.policyId.toString(),
        policyAccount: config.policyAccount,
        tokenTransactionHash: tokenLog.transactionHash,
        policyTransactionHash: policyLog.transactionHash,
        policyAccountTransactionHash: policyAccountLog.transactionHash,
        linkTransactionHash: linkLog.transactionHash,
      };
    }

    return null;
  }, "stablecoin creation, policy creation, and policy link were not observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
