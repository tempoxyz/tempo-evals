const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, memoEncodings, sameAddress, transactionKeyId, waitForEvidence } = require("../tempo");

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_ACCESS_KEY_PRIVATE_KEY: config.accessKeyPrivateKey,
    TEMPO_ACCESS_KEY_LIMIT: config.accessKeyLimit,
    TEMPO_ACCESS_KEY_PERIOD_SECONDS: config.accessKeyPeriodSeconds,
  };
}

async function verify({ client, config, fromBlock }) {
  const payer = privateKeyToAccount(config.payerPrivateKey).address;
  const amount = parseUnits(config.amount, config.decimals);
  const limit = parseUnits(config.accessKeyLimit, config.decimals);
  const maxRemainingAfterTransfer = limit - amount;
  const memos = memoEncodings(config.memo);

  const authorizedEvent = parseAbiItem(
    "event KeyAuthorized(address indexed account, address indexed publicKey, uint8 signatureType, uint64 expiry)",
  );
  const spendEvent = parseAbiItem(
    "event AccessKeySpend(address indexed account, address indexed publicKey, address indexed token, uint256 amount, uint256 remainingLimit)",
  );
  const transferEvent = parseAbiItem(
    "event TransferWithMemo(address indexed from, address indexed to, uint256 value, bytes32 indexed memo)",
  );

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const keyLogs = await client.getLogs({
      address: config.accountKeychain,
      event: authorizedEvent,
      args: { account: payer },
      fromBlock,
      toBlock: latestBlock,
    });
    const keyLog = keyLogs[0];
    if (!keyLog) return null;

    const spendLogs = await client.getLogs({
      address: config.accountKeychain,
      event: spendEvent,
      args: {
        account: payer,
        publicKey: keyLog.args.publicKey,
        token: config.token,
      },
      fromBlock,
      toBlock: latestBlock,
    });
    const spendLog = spendLogs.find(
      (log) =>
        log.args.amount === amount &&
        log.args.remainingLimit > 0n &&
        log.args.remainingLimit <= maxRemainingAfterTransfer,
    );
    if (!spendLog) return null;

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
    const transferLog = transferLogs.find(
      (log) => log.args.value === amount && log.transactionHash === spendLog.transactionHash,
    );
    if (!transferLog) return null;

    const transaction = await client.request({
      method: "eth_getTransactionByHash",
      params: [transferLog.transactionHash],
    });
    if (!sameAddress(transactionKeyId(transaction), keyLog.args.publicKey)) return null;

    return blockEvidence(transferLog, {
      accessKey: keyLog.args.publicKey,
      keyAuthorizationTransactionHash: keyLog.transactionHash,
      remainingLimit: spendLog.args.remainingLimit.toString(),
      spendTransactionHash: spendLog.transactionHash,
    });
  }, "limited access key spend and matching transfer were not observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
