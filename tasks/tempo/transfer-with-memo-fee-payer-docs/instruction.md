<!-- AUTO-GENERATED FROM tasks/tempo/_templates/transfer-with-memo-fee-payer/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Transfer With Memo And Fee Payer

Build a minimal TypeScript project that sends a Tempo stablecoin payment with a memo and a separate fee payer.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| RPC URL | `TEMPO_RPC_URL` | `http://tempo-localnet:8545` |
| Payer private key | `TEMPO_PAYER_PRIVATE_KEY` | provided |
| Token address | `TEMPO_TOKEN` | `0x20c0000000000000000000000000000000000001` |
| Recipient address | `TEMPO_RECIPIENT` | `0x1111111111111111111111111111111111111111` |
| Transfer amount | `TEMPO_AMOUNT` | `0.19` |
| Token decimals | `TEMPO_DECIMALS` | `6` |
| Transfer memo | `TEMPO_MEMO` | `TEMPO-FEEPAYER-001` |
| Fee payer private key | `TEMPO_FEE_PAYER_PRIVATE_KEY` | provided |
| Fee token | `TEMPO_FEE_TOKEN` | `0x20c0000000000000000000000000000000000001` |

## Tempo Access Profile

Tempo docs are available through the local docs service at `TEMPO_DOCS_URL` (http://tempo-docs:3000/developers). Use those docs for Tempo-specific APIs and examples. Do not use WebSearch, WebFetch, public docs sites, or public RPC endpoints.

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all eval and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local eval checks must use the provided environment variables.

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run eval`
