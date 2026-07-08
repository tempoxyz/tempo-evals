<!-- AUTO-GENERATED FROM tasks/tempo/_templates/set-fee-token/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Set Fee Token

Build a minimal TypeScript project that sets the account's default Tempo fee token to AlphaUSD.

## Parameters

* Use `TEMPO_FEE_TOKEN` as the fee token to set.

## Tempo Access Profile

Tempo docs are available through the local docs service at `TEMPO_DOCS_URL` (http://tempo-docs:3000/developers). Use those docs for Tempo-specific APIs and examples. Do not use WebSearch, WebFetch, public docs sites, or public RPC endpoints.

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all example and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local example checks must use the provided environment variables.

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run example`
