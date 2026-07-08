<!-- AUTO-GENERATED FROM tasks/tempo/_templates/transfer-with-memo-fee-payer/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Transfer With Memo And Fee Payer

Build a minimal TypeScript project that sends a Tempo stablecoin payment with a 32-byte memo and a separate fee payer.

## Parameters

* Read the transfer memo from `TEMPO_MEMO`.
* Use `TEMPO_FEE_PAYER_PRIVATE_KEY` as the transaction fee payer.
* Use `TEMPO_FEE_TOKEN` as the fee token.

## Tempo Access Profile

The official Tempo MCP server is configured as `tempo`. Use it if your agent runtime exposes MCP tools; do not use WebSearch, WebFetch, or public RPC endpoints.

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all example and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local example checks must use the provided environment variables.

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run example`
