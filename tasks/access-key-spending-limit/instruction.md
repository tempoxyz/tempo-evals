# Tempo Access Key Spending Limit

Build a minimal TypeScript project in `/app` that authorizes a Tempo access
key with a per-token spending limit, then uses that access key to send a
stablecoin payment within the limit.

Use environment variables for all values:

- `TEMPO_RPC_URL`
- `TEMPO_PAYER_PRIVATE_KEY`
- `TEMPO_ACCESS_KEY_PRIVATE_KEY`
- `TEMPO_ACCESS_KEY_LIMIT`
- `TEMPO_ACCESS_KEY_PERIOD_SECONDS`
- `TEMPO_TOKEN`
- `TEMPO_RECIPIENT`
- `TEMPO_AMOUNT`
- `TEMPO_DECIMALS`
- `TEMPO_MEMO`

## Tempo Access Profile

No Tempo docs URL or Tempo MCP server is provided for this profile. Do not use WebSearch, WebFetch, or external documentation; solve from the prompt, local package APIs, and local files only.

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all build, run, and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local build/run checks must use the provided environment variables.

Requirements:

- Put the submission directly in `/app`.
- Include `package.json`.
- Include `tsconfig.json`.
- Put the runtime source in `src/index.ts`.
- Include scripts named exactly `build` and `run`.
- `npm run build` must typecheck or compile.
- `npm run run` must authorize the access key with a spending limit for `TEMPO_TOKEN`.
- `npm run run` must use the access key, not the payer root key, for the transfer.
- The transfer amount must be within `TEMPO_ACCESS_KEY_LIMIT`.
- Include the memo on the transfer.
- Do not edit `/tests`, `/logs`, or `/solution`.
