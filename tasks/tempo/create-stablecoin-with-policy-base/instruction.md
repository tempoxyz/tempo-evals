<!-- AUTO-GENERATED FROM tasks/tempo/_templates/create-stablecoin-with-policy/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Create Stablecoin With Transfer Policy

Build a minimal TypeScript project that creates a TIP-20 stablecoin,
creates a Tempo transfer policy, and links that policy to the new token.

## Parameters

* Create the stablecoin with currency `TEMPO_STABLECOIN_CURRENCY`.
* Create a TIP-403 policy of type `TEMPO_POLICY_TYPE` including `TEMPO_POLICY_ACCOUNT`.

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all example and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local example checks must use the provided environment variables.

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run example`
