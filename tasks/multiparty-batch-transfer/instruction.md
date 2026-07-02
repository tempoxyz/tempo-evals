# Tempo Multiparty Batch Transfer

Build a minimal TypeScript project in `/app` that sends payments to multiple
recipients in one Tempo transaction.

Use environment variables for all values:

- `TEMPO_RPC_URL`
- `TEMPO_PAYER_PRIVATE_KEY`
- `TEMPO_TOKEN`
- `TEMPO_MULTI_RECIPIENTS`
- `TEMPO_MULTI_AMOUNTS`
- `TEMPO_DECIMALS`

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
- Parse `TEMPO_MULTI_RECIPIENTS` and `TEMPO_MULTI_AMOUNTS` as comma-separated lists.
- Send each configured amount of `TEMPO_TOKEN` to the corresponding recipient.
- All configured payments must be included in a single Tempo transaction using multiple calls.
- Do not edit `/tests`, `/logs`, or `/solution`.
