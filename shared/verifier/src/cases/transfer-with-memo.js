// AUTO-GENERATED FROM shared/verifier/src/cases/transfer-with-memo.js BY npm run sync. DO NOT EDIT MANUALLY.
const { parseAbiItem, parseUnits } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { blockEvidence, memoEncodings, sameAddress, waitForEvidence } = require("../tempo");

function runtimeEnv(config) {
  const env = defaultRuntimeEnv(config);
  if (config.feePayerPrivateKey) {
    env.TEMPO_FEE_PAYER_PRIVATE_KEY = config.feePayerPrivateKey;
    env.TEMPO_FEE_TOKEN = config.feeToken;
  }
  return env;
}

async function assertFeePayerEnvelope(client, config, transactionHash) {
  if (!config.feePayerPrivateKey) return null;

  const feePayer = privateKeyToAccount(config.feePayerPrivateKey).address;
  const transaction = await client.request({
    method: "eth_getTransactionByHash",
    params: [transactionHash],
  });

  if (
    transaction?.type !== "0x76" ||
    !transaction.feePayerSignature ||
    !sameAddress(transaction?.feeToken, config.feeToken)
  ) {
    throw new Error("matching transfer did not use a sponsored Tempo fee-payer envelope");
  }

  return {
    feePayer,
    feeToken: transaction.feeToken,
  };
}

async function verify({ client, config, fromBlock }) {
  const payer = privateKeyToAccount(config.payerPrivateKey).address;
  const expectedValue = parseUnits(config.amount, config.decimals);
  const event = parseAbiItem(
    "event TransferWithMemo(address indexed from, address indexed to, uint256 value, bytes32 indexed memo)",
  );
  const memos = memoEncodings(config.memo);

  return waitForEvidence(config, async () => {
    const latestBlock = await client.getBlockNumber();
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

    const match = logs.find((log) => log.args.value === expectedValue);
    if (match) {
      const feePayer = await assertFeePayerEnvelope(client, config, match.transactionHash);
      return blockEvidence(match, { ...feePayer });
    }

    return null;
  }, "no matching TransferWithMemo event observed");
}

module.exports = {
  runtimeEnv,
  verify,
};
