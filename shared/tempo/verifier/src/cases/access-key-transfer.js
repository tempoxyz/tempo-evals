const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { Actions } = require("viem/tempo");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, sameAddress, waitForEvidence } = require("../tempo");

const accountKeychain = "0xaAAAaaAA00000000000000000000000000000000";

function runtimeEnv(config) {
  return defaultRuntimeEnv(config);
}

async function accessKeyEnvelope(client, transactionHash, payer) {
  const transaction = await client.request({
    method: "eth_getTransactionByHash",
    params: [transactionHash],
  });
  const signature = transaction?.signature;
  const keyId = signature?.keyId;

  if (
    transaction?.type !== "0x76" ||
    !sameAddress(signature?.userAddress, payer) ||
    !keyId
  ) {
    return null;
  }

  return {
    accessKey: keyId,
    keyType: signature.signature?.type ?? signature.keyType ?? "unknown",
  };
}

async function hasAuthorizedAccessKey(client, payer, accessKey) {
  try {
    const metadata = await Actions.accessKey.getMetadata(client, {
      account: payer,
      accessKey,
    });
    const now = BigInt(Math.floor(Date.now() / 1000));
    return (
      sameAddress(metadata.address, accessKey) &&
      !metadata.isRevoked &&
      metadata.expiry > now
    );
  } catch {
    return false;
  }
}

async function wasAuthorized(client, payer, accessKey, fromBlock, toBlock, keyAuthorizedEvent) {
  const keyLogs = await client.getLogs({
    address: accountKeychain,
    event: keyAuthorizedEvent,
    args: {
      account: payer,
      publicKey: accessKey,
    },
    fromBlock,
    toBlock,
  });

  return keyLogs.length > 0 || (await hasAuthorizedAccessKey(client, payer, accessKey));
}

async function verify({ client, config, fromBlock }) {
  const payer = privateKeyToAccount(config.payerPrivateKey).address;
  const expectedValue = parseUnits(config.amount, config.decimals);
  const transferEvent = parseAbiItem(
    "event Transfer(address indexed from, address indexed to, uint256 value)",
  );
  const keyAuthorizedEvent = parseAbiItem(
    "event KeyAuthorized(address indexed account, address indexed publicKey, uint8 signatureType, uint64 expiry)",
  );

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const transferLogs = await client.getLogs({
      address: config.token,
      event: transferEvent,
      args: {
        from: payer,
        to: config.recipient,
      },
      fromBlock,
      toBlock: latestBlock,
    });

    for (const log of transferLogs) {
      if (log.args.value !== expectedValue) continue;

      const envelope = await accessKeyEnvelope(client, log.transactionHash, payer);
      if (!envelope) continue;

      const authorized = await wasAuthorized(
        client,
        payer,
        envelope.accessKey,
        fromBlock,
        latestBlock,
        keyAuthorizedEvent,
      );
      if (authorized) return blockEvidence(log, envelope);
    }

    return null;
  }, "no matching transfer submitted by an authorized access key observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
