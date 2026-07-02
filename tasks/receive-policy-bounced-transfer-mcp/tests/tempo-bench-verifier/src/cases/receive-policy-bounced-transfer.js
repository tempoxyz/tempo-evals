const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, sameAddress, waitForEvidence } = require("../tempo");

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_RECIPIENT_PRIVATE_KEY: config.recipientPrivateKey,
    TEMPO_RECEIVE_POLICY_SENDER_POLICY_ID: config.receivePolicySenderPolicyId.toString(),
    TEMPO_RECEIVE_POLICY_TOKEN_POLICY_ID: config.receivePolicyTokenPolicyId.toString(),
  };
}

async function verify({ client, config, fromBlock }) {
  const recipient = privateKeyToAccount(config.recipientPrivateKey).address;
  const expectedValue = parseUnits(config.amount, config.decimals);
  const policyEvent = parseAbiItem(
    "event ReceivePolicyUpdated(address indexed account, uint64 senderPolicyId, uint64 tokenFilterId, address recoveryAuthority)",
  );
  const blockedEvent = parseAbiItem(
    "event TransferBlocked(address indexed token, address indexed receiver, uint64 indexed blockedNonce, uint256 amount, uint8 receiptVersion, bytes receipt)",
  );

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
    const policyLogs = await client.getLogs({
      address: config.tip403Registry,
      event: policyEvent,
      args: { account: recipient },
      fromBlock,
      toBlock: latestBlock,
    });
    const policyLog = policyLogs.find(
      (log) =>
        log.args.senderPolicyId === config.receivePolicySenderPolicyId &&
        log.args.tokenFilterId === config.receivePolicyTokenPolicyId &&
        sameAddress(log.args.recoveryAuthority, recipient),
    );
    if (!policyLog) return null;

    const blockedLogs = await client.getLogs({
      address: config.receivePolicyGuard,
      event: blockedEvent,
      args: {
        token: config.token,
        receiver: recipient,
      },
      fromBlock,
      toBlock: latestBlock,
    });
    const blockedLog = blockedLogs.find((log) => log.args.amount === expectedValue);
    if (!blockedLog) return null;

    return blockEvidence(blockedLog, {
      policyTransactionHash: policyLog.transactionHash,
      recipient,
      blockedNonce: blockedLog.args.blockedNonce.toString(),
    });
  }, "receive policy update and blocked transfer were not observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
