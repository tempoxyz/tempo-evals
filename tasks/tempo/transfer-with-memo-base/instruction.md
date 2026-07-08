<!-- AUTO-GENERATED FROM tasks/tempo/_templates/transfer-with-memo/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Transfer With Memo

Build a minimal TypeScript project that sends a Tempo stablecoin payment with a memo.

## Parameters

* Read the transfer memo from `TEMPO_MEMO`.

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all example and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local example checks must use the provided environment variables.

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run example`
