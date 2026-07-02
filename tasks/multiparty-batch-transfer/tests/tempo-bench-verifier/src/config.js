function env(name, fallback = "") {
  const value = process.env[name];
  return value && value.length > 0 ? value : fallback;
}

function requiredEnv(name) {
  const value = env(name);
  if (!value) throw new Error(`missing required environment variable: ${name}`);
  return value;
}

function numberEnv(name) {
  const value = Number(requiredEnv(name));
  if (!Number.isFinite(value)) throw new Error(`invalid numeric environment variable: ${name}`);
  return value;
}

function listEnv(name, fallback = "") {
  return env(name, fallback)
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
}

function readConfig() {
  return {
    caseId: env("TEMPO_BENCH_CASE", "transfer-with-memo"),
    workspace: env("TEMPO_BENCH_WORKSPACE", "/app"),
    logDir: env("TEMPO_BENCH_LOG_DIR", "/logs/verifier"),
    rpcUrl: requiredEnv("TEMPO_RPC_URL"),
    token: requiredEnv("TEMPO_TOKEN"),
    feeToken: env("TEMPO_FEE_TOKEN", env("TEMPO_TOKEN")),
    feeManager: env("TEMPO_FEE_MANAGER", "0xfeec000000000000000000000000000000000000"),
    tip20Factory: env("TEMPO_TIP20_FACTORY", "0x20fc000000000000000000000000000000000000"),
    tip403Registry: env("TEMPO_TIP403_REGISTRY", "0x403c000000000000000000000000000000000000"),
    stablecoinDex: env("TEMPO_STABLECOIN_DEX", "0xdec0000000000000000000000000000000000000"),
    accountKeychain: env("TEMPO_ACCOUNT_KEYCHAIN", "0xaAAAaaAA00000000000000000000000000000000"),
    receivePolicyGuard: env("TEMPO_RECEIVE_POLICY_GUARD", "0xB10C000000000000000000000000000000000000"),
    payerPrivateKey: requiredEnv("TEMPO_PAYER_PRIVATE_KEY"),
    accessKeyPrivateKey: env("TEMPO_ACCESS_KEY_PRIVATE_KEY"),
    recipientPrivateKey: env("TEMPO_RECIPIENT_PRIVATE_KEY"),
    feePayerPrivateKey: env("TEMPO_FEE_PAYER_PRIVATE_KEY"),
    faucetPrivateKey: env("TEMPO_FAUCET_PRIVATE_KEY", env("TEMPO_PAYER_PRIVATE_KEY")),
    dexMakerPrivateKey: env("TEMPO_DEX_MAKER_PRIVATE_KEY", env("TEMPO_PAYER_PRIVATE_KEY")),
    recipient: requiredEnv("TEMPO_RECIPIENT"),
    amount: requiredEnv("TEMPO_AMOUNT"),
    memo: requiredEnv("TEMPO_MEMO"),
    decimals: numberEnv("TEMPO_DECIMALS"),
    stablecoinName: env("TEMPO_STABLECOIN_NAME", "Tempo Bench USD"),
    stablecoinSymbol: env("TEMPO_STABLECOIN_SYMBOL", "TBUSD"),
    stablecoinCurrency: env("TEMPO_STABLECOIN_CURRENCY", "USD"),
    stablecoinSalt: env("TEMPO_STABLECOIN_SALT"),
    policyType: env("TEMPO_POLICY_TYPE", "blacklist"),
    policyAccount: env("TEMPO_POLICY_ACCOUNT", env("TEMPO_RECIPIENT")),
    accessKeyLimit: env("TEMPO_ACCESS_KEY_LIMIT"),
    accessKeyPeriodSeconds: env("TEMPO_ACCESS_KEY_PERIOD_SECONDS"),
    receivePolicySenderPolicyId: BigInt(env("TEMPO_RECEIVE_POLICY_SENDER_POLICY_ID", "0")),
    receivePolicyTokenPolicyId: BigInt(env("TEMPO_RECEIVE_POLICY_TOKEN_POLICY_ID", "1")),
    swapTokenIn: env("TEMPO_SWAP_TOKEN_IN", env("TEMPO_TOKEN")),
    swapTokenOut: env("TEMPO_SWAP_TOKEN_OUT", "0x20c0000000000000000000000000000000000002"),
    swapAmountIn: env("TEMPO_SWAP_AMOUNT_IN", env("TEMPO_AMOUNT")),
    swapMinAmountOut: env("TEMPO_SWAP_MIN_AMOUNT_OUT", "0"),
    multiRecipients: listEnv("TEMPO_MULTI_RECIPIENTS", env("TEMPO_RECIPIENT")),
    multiAmounts: listEnv("TEMPO_MULTI_AMOUNTS", env("TEMPO_AMOUNT")),
    submissionTimeoutMs: Number(env("TEMPO_BENCH_SUBMISSION_TIMEOUT_MS", "180000")),
    rpcWaitMs: Number(env("TEMPO_BENCH_RPC_WAIT_MS", "60000")),
    logWaitMs: Number(env("TEMPO_BENCH_LOG_WAIT_MS", "30000")),
  };
}

function redactedConfig(config) {
  return {
    ...config,
    receivePolicySenderPolicyId: config.receivePolicySenderPolicyId.toString(),
    receivePolicyTokenPolicyId: config.receivePolicyTokenPolicyId.toString(),
    payerPrivateKey: "<redacted>",
    accessKeyPrivateKey: config.accessKeyPrivateKey ? "<redacted>" : "",
    recipientPrivateKey: config.recipientPrivateKey ? "<redacted>" : "",
    feePayerPrivateKey: config.feePayerPrivateKey ? "<redacted>" : "",
    faucetPrivateKey: config.faucetPrivateKey ? "<redacted>" : "",
    dexMakerPrivateKey: config.dexMakerPrivateKey ? "<redacted>" : "",
  };
}

module.exports = {
  readConfig,
  redactedConfig,
};
