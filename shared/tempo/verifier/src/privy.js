const PRIVY_LOOKUP_FAILURE = "Privy API lookup failed";

function requirePrivyAuth(config) {
  if (config.privyAppId && config.privyAppSecret) return;
  const error = new Error(
    "missing Privy credentials: set PRIVY_APP_ID and PRIVY_APP_SECRET",
  );
  error.phase = "privy-auth";
  error.expected = "PRIVY_APP_ID and PRIVY_APP_SECRET are set for the verifier";
  throw error;
}

function privyHeaders(config) {
  const basic = Buffer.from(
    `${config.privyAppId}:${config.privyAppSecret}`,
  ).toString("base64");
  return {
    Authorization: `Basic ${basic}`,
    "privy-app-id": config.privyAppId,
    "Content-Type": "application/json",
  };
}

async function privyRequest(config, method, path, body) {
  const response = await fetch(`${config.privyApiUrl}${path}`, {
    method,
    headers: privyHeaders(config),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let parsed = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    parsed = { raw: text };
  }
  return { status: response.status, body: parsed };
}

async function getWallet(config, walletId) {
  const { status, body } = await privyRequest(
    config,
    "GET",
    `/v1/wallets/${encodeURIComponent(walletId)}`,
  );
  if (status !== 200) {
    throw new Error(`${PRIVY_LOOKUP_FAILURE}: wallet ${walletId} returned status ${status}`);
  }
  return body;
}

async function getPolicy(config, policyId) {
  const { status, body } = await privyRequest(
    config,
    "GET",
    `/v1/policies/${encodeURIComponent(policyId)}`,
  );
  if (status !== 200) {
    throw new Error(`${PRIVY_LOOKUP_FAILURE}: policy ${policyId} returned status ${status}`);
  }
  return body;
}

async function walletRpc(config, walletId, payload) {
  return privyRequest(
    config,
    "POST",
    `/v1/wallets/${encodeURIComponent(walletId)}/rpc`,
    payload,
  );
}

module.exports = {
  getPolicy,
  getWallet,
  requirePrivyAuth,
  walletRpc,
};
