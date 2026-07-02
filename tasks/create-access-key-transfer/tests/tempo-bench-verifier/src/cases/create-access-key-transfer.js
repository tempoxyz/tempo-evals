const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, memoEncodings, sameAddress, transactionKeyId, waitForEvidence } = require("../tempo");

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_ACCESS_KEY_PRIVATE_KEY: config.accessKeyPrivateKey,
  };
}

async function findAuthorizedKey(client, config, fromBlock, latestBlock, payer) {
  const event = parseAbiItem(
    "event KeyAuthorized(address indexed account, address indexed publicKey, uint8 signatureType, uint64 expiry)",
  );
  const logs = await client.getLogs({
    address: config.accountKeychain,
    event,
    args: { account: payer },
    fromBlock,
    toBlock: latestBlock,
  });
  return logs[0] || null;
}

async function findMatchingTransfer(client, config, fromBlock, latestBlock, payer) {
  const expectedValue = parseUnits(config.amount, config.decimals);
  const event = parseAbiItem(
    "event TransferWithMemo(address indexed from, address indexed to, uint256 value, bytes32 indexed memo)",
  );
  const memos = memoEncodings(config.memo);
  const logs = (
    await Promise.all(
      memos.map((memo) =>
        client.getLogs({
          address: config.token,
          event,
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
  return logs.find((log) => log.args.value === expectedValue) || null;
}

async function verify({ client, config, fromBlock }) {
  const payer = privateKeyToAccount(config.payerPrivateKey).address;

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const keyLog = await findAuthorizedKey(client, config, fromBlock, latestBlock, payer);
    if (!keyLog) return null;

    const transferLog = await findMatchingTransfer(client, config, fromBlock, latestBlock, payer);
    if (!transferLog) return null;

    const transaction = await client.request({
      method: "eth_getTransactionByHash",
      params: [transferLog.transactionHash],
    });
    if (!sameAddress(transactionKeyId(transaction), keyLog.args.publicKey)) {
      return null;
    }

    return blockEvidence(transferLog, {
      accessKey: keyLog.args.publicKey,
      keyAuthorizationTransactionHash: keyLog.transactionHash,
      keyType: transaction?.keyType,
    });
  }, "authorized access key did not execute the expected memo transfer");
}

module.exports = {
  runtimeEnv,
  verify,
};
