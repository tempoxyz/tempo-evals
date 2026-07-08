<!-- AUTO-GENERATED FROM tasks/tempo/_templates/faucet-funded-transfer/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Faucet Funded Transfer

Build a minimal TypeScript project that funds a wallet with Tempo's faucet, then sends an AlphaUSD transfer from that funded wallet.

## Parameters

* Use `TEMPO_FAUCET_PRIVATE_KEY` for the wallet that calls the faucet.

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all example and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local example checks must use the provided environment variables.

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run example`
