<!-- AUTO-GENERATED FROM tasks/tempo/_templates/set-fee-token/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Set Fee Token

Build a minimal TypeScript project that sets the account's default Tempo fee token to AlphaUSD.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| RPC URL | `TEMPO_RPC_URL` | `http://tempo-localnet:8545` |
| Payer private key | `TEMPO_PAYER_PRIVATE_KEY` | provided |
| Fee token to set | `TEMPO_FEE_TOKEN` | `0x20c0000000000000000000000000000000000001` |

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all eval and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local eval checks must use the provided environment variables.

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run eval`
