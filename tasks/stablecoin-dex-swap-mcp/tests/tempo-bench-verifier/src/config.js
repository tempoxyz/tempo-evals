function env(name, fallback = "") {
  const value = process.env[name];
  return value && value.length > 0 ? value : fallback;
}

function requiredEnv(name) {
  const value = env(name);
  if (!value) throw new Error(`missing required environment variable: ${name}`);
  return value;
}

function optionalNumberEnv(name) {
  const value = env(name);
  if (!value) return undefined;
  const numberValue = Number(value);
  if (!Number.isFinite(numberValue)) throw new Error(`invalid numeric environment variable: ${name}`);
  return numberValue;
}

const fieldEnvNames = {
  amount: "TEMPO_AMOUNT",
  decimals: "TEMPO_DECIMALS",
  dexMakerPrivateKey: "TEMPO_DEX_MAKER_PRIVATE_KEY",
  faucetPrivateKey: "TEMPO_FAUCET_PRIVATE_KEY",
  feeToken: "TEMPO_FEE_TOKEN",
  memo: "TEMPO_MEMO",
  payerPrivateKey: "TEMPO_PAYER_PRIVATE_KEY",
  policyAccount: "TEMPO_POLICY_ACCOUNT",
  policyType: "TEMPO_POLICY_TYPE",
  recipient: "TEMPO_RECIPIENT",
  stablecoinCurrency: "TEMPO_STABLECOIN_CURRENCY",
  stablecoinDex: "TEMPO_STABLECOIN_DEX",
  stablecoinName: "TEMPO_STABLECOIN_NAME",
  stablecoinSalt: "TEMPO_STABLECOIN_SALT",
  stablecoinSymbol: "TEMPO_STABLECOIN_SYMBOL",
  swapAmountIn: "TEMPO_SWAP_AMOUNT_IN",
  swapMinAmountOut: "TEMPO_SWAP_MIN_AMOUNT_OUT",
  swapTokenIn: "TEMPO_SWAP_TOKEN_IN",
  swapTokenOut: "TEMPO_SWAP_TOKEN_OUT",
  token: "TEMPO_TOKEN",
};

const requiredFieldsByCase = {
  "create-stablecoin-with-policy": [
    "payerPrivateKey",
    "token",
    "stablecoinName",
    "stablecoinSymbol",
    "stablecoinCurrency",
    "stablecoinSalt",
    "policyType",
    "policyAccount",
  ],
  "faucet-funded-transfer": ["faucetPrivateKey", "token", "recipient", "amount", "decimals"],
  "set-fee-token": ["payerPrivateKey", "feeToken"],
  "stablecoin-dex-swap": [
    "payerPrivateKey",
    "dexMakerPrivateKey",
    "stablecoinDex",
    "swapTokenIn",
    "swapTokenOut",
    "swapAmountIn",
    "swapMinAmountOut",
    "decimals",
  ],
  "transfer-with-memo": ["payerPrivateKey", "token", "recipient", "amount", "memo", "decimals"],
};

function requireCaseFields(config) {
  const requiredFields = requiredFieldsByCase[config.caseId];
  if (!requiredFields) throw new Error(`unsupported TEMPO_BENCH_CASE: ${config.caseId}`);

  for (const field of requiredFields) {
    const value = config[field];
    if (value === undefined || value === "") {
      throw new Error(`missing required environment variable: ${fieldEnvNames[field] ?? field}`);
    }
  }
}

function readConfig() {
  const config = {
    caseId: env("TEMPO_BENCH_CASE", "transfer-with-memo"),
    workspace: env("TEMPO_BENCH_WORKSPACE", "/app"),
    logDir: env("TEMPO_BENCH_LOG_DIR", "/logs/verifier"),
    rpcUrl: requiredEnv("TEMPO_RPC_URL"),
    token: env("TEMPO_TOKEN"),
    feeToken: env("TEMPO_FEE_TOKEN", env("TEMPO_TOKEN")),
    feeManager: env("TEMPO_FEE_MANAGER", "0xfeec000000000000000000000000000000000000"),
    tip20Factory: env("TEMPO_TIP20_FACTORY", "0x20fc000000000000000000000000000000000000"),
    tip403Registry: env("TEMPO_TIP403_REGISTRY", "0x403c000000000000000000000000000000000000"),
    stablecoinDex: env("TEMPO_STABLECOIN_DEX", "0xdec0000000000000000000000000000000000000"),
    payerPrivateKey: env("TEMPO_PAYER_PRIVATE_KEY"),
    feePayerPrivateKey: env("TEMPO_FEE_PAYER_PRIVATE_KEY"),
    faucetPrivateKey: env("TEMPO_FAUCET_PRIVATE_KEY", env("TEMPO_PAYER_PRIVATE_KEY")),
    dexMakerPrivateKey: env("TEMPO_DEX_MAKER_PRIVATE_KEY", env("TEMPO_PAYER_PRIVATE_KEY")),
    recipient: env("TEMPO_RECIPIENT"),
    amount: env("TEMPO_AMOUNT"),
    memo: env("TEMPO_MEMO"),
    decimals: optionalNumberEnv("TEMPO_DECIMALS"),
    stablecoinName: env("TEMPO_STABLECOIN_NAME", "Tempo Bench USD"),
    stablecoinSymbol: env("TEMPO_STABLECOIN_SYMBOL", "TBUSD"),
    stablecoinCurrency: env("TEMPO_STABLECOIN_CURRENCY", "USD"),
    stablecoinSalt: env("TEMPO_STABLECOIN_SALT"),
    policyType: env("TEMPO_POLICY_TYPE", "blacklist"),
    policyAccount: env("TEMPO_POLICY_ACCOUNT", env("TEMPO_RECIPIENT")),
    swapTokenIn: env("TEMPO_SWAP_TOKEN_IN", env("TEMPO_TOKEN")),
    swapTokenOut: env("TEMPO_SWAP_TOKEN_OUT", "0x20c0000000000000000000000000000000000002"),
    swapAmountIn: env("TEMPO_SWAP_AMOUNT_IN", env("TEMPO_AMOUNT")),
    swapMinAmountOut: env("TEMPO_SWAP_MIN_AMOUNT_OUT", "0"),
    submissionTimeoutMs: Number(env("TEMPO_BENCH_SUBMISSION_TIMEOUT_MS", "180000")),
    rpcWaitMs: Number(env("TEMPO_BENCH_RPC_WAIT_MS", "60000")),
    logWaitMs: Number(env("TEMPO_BENCH_LOG_WAIT_MS", "30000")),
  };
  requireCaseFields(config);
  return config;
}

function redactedConfig(config) {
  return {
    ...config,
    payerPrivateKey: "<redacted>",
    feePayerPrivateKey: config.feePayerPrivateKey ? "<redacted>" : "",
    faucetPrivateKey: config.faucetPrivateKey ? "<redacted>" : "",
    dexMakerPrivateKey: config.dexMakerPrivateKey ? "<redacted>" : "",
  };
}

module.exports = {
  readConfig,
  redactedConfig,
};
