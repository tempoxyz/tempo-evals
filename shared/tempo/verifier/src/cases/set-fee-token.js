// SYNCED FROM shared/tempo/verifier/src/cases/set-fee-token.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
const { parseAbi } = require("viem");
const { privateKeyToAccount } = require("viem/accounts");
const { defaultRuntimeEnv } = require("../submission");
const { sameAddress, waitForEvidence } = require("../tempo");

function runtimeEnv(config) {
  return {
    ...defaultRuntimeEnv(config),
    TEMPO_FEE_MANAGER: config.feeManager,
    TEMPO_FEE_TOKEN: config.feeToken,
  };
}

async function verify({ client, config, fromBlock }) {
  const payer = privateKeyToAccount(config.payerPrivateKey).address;
  const abi = parseAbi(["function userTokens(address user) view returns (address)"]);

  return waitForEvidence(config, async () => {
    const token = await client.readContract({
      address: config.feeManager,
      abi,
      functionName: "userTokens",
      args: [payer],
    });

    if (sameAddress(token, config.feeToken)) {
      const latestBlock = await client.getBlockNumber();
      return {
        blockNumber: latestBlock.toString(),
        token,
      };
    }

    return null;
  }, "fee token was not set for payer");
}

module.exports = {
  runtimeEnv,
  verify,
};
