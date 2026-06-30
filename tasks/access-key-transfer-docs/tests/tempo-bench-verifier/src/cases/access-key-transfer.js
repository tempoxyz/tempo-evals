const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, memoEncodings, waitForEvidence } = require("../tempo");

function required(value, name) {
  if (!value) throw new Error(`${name} is required`);
  return value;
}

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_ACCESS_KEY_PRIVATE_KEY: required(
      config.accessKeyPrivateKey,
      "TEMPO_ACCESS_KEY_PRIVATE_KEY",
    ),
    TEMPO_ACCESS_KEY_LIMIT: config.accessKeyLimit,
    TEMPO_ACCOUNT_KEYCHAIN: config.accountKeychain,
  };
}

async function verify({ client, config, fromBlock }) {
  const payer = privateKeyToAccount(config.payerPrivateKey).address;
  const accessKey = privateKeyToAccount(
    required(config.accessKeyPrivateKey, "TEMPO_ACCESS_KEY_PRIVATE_KEY"),
  ).address;
  const expectedValue = parseUnits(config.amount, config.decimals);
  const transferEvent = parseAbiItem(
    "event TransferWithMemo(address indexed from, address indexed to, uint256 value, bytes32 indexed memo)",
  );
  const keyAuthorizedEvent = parseAbiItem(
    "event KeyAuthorized(address indexed account, address indexed publicKey, uint8 signatureType, uint64 expiry)",
  );
  const accessKeySpendEvent = parseAbiItem(
    "event AccessKeySpend(address indexed account, address indexed publicKey, address indexed token, uint256 amount, uint256 remainingLimit)",
  );
  const memos = memoEncodings(config.memo);

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const keyAuthorizedLogs = await client.getLogs({
      address: config.accountKeychain,
      event: keyAuthorizedEvent,
      args: {
        account: payer,
        publicKey: accessKey,
      },
      fromBlock,
      toBlock: latestBlock,
    });
    if (keyAuthorizedLogs.length === 0) return null;

    const transferLogs = (
      await Promise.all(
        memos.map((memo) =>
          client.getLogs({
            address: config.token,
            event: transferEvent,
            args: {
              from: payer,
              to: config.recipient,
              memo,
            },
            fromBlock,
            toBlock: latestBlock,
          }),
        ),
      )
    ).flat();
    const transfer = transferLogs.find((log) => log.args.value === expectedValue);
    if (!transfer) return null;

    const spendLogs = await client.getLogs({
      address: config.accountKeychain,
      event: accessKeySpendEvent,
      args: {
        account: payer,
        publicKey: accessKey,
        token: config.token,
      },
      fromBlock,
      toBlock: latestBlock,
    });
    const spend = spendLogs.find(
      (log) =>
        log.transactionHash === transfer.transactionHash &&
        log.args.amount === expectedValue,
    );
    if (!spend) return null;

    return blockEvidence(transfer, {
      accessKey,
      keyAuthorizedTransactionHash: keyAuthorizedLogs[0].transactionHash,
      accessKeySpendTransactionHash: spend.transactionHash,
      remainingLimit: spend.args.remainingLimit.toString(),
    });
  }, "access key authorization and matching access-key memo transfer were not observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
