<!-- AUTO-GENERATED FROM tasks/tempo-v1/_templates/transfer-batched/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Batched Transfer

Build a minimal TypeScript project that pays every configured recipient the same Tempo stablecoin amount in one transaction.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| RPC URL | `TEMPO_RPC_URL` | `http://tempo-localnet:8545` |
| Payer private key | `TEMPO_PAYER_PRIVATE_KEY` | provided |
| Token address | `TEMPO_TOKEN` | `0x20c0000000000000000000000000000000000001` |
| Recipient addresses | `TEMPO_RECIPIENTS` | JSON array provided |
| Amount per recipient | `TEMPO_AMOUNT` | `0.01` |
| Token decimals | `TEMPO_DECIMALS` | `6` |

## Tempo Documentation

Tempo documentation is available publicly at https://docs.tempo.xyz. Use it for Tempo-specific APIs and examples.

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all eval and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local eval checks must use the provided environment variables.

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* Use a native Tempo batch transaction: encode a TIP-20 `transfer` call for every recipient and submit them together through `calls`.
* The script should be runnable by `npm run eval`.
