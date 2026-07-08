# Tempo Transfer With Memo

Build a minimal TypeScript project that sends a Tempo stablecoin payment with a memo.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| RPC URL | `TEMPO_RPC_URL` | `http://tempo-localnet:8545` |
| Payer private key | `TEMPO_PAYER_PRIVATE_KEY` | provided |
| Token address | `TEMPO_TOKEN` | `0x20c0000000000000000000000000000000000001` |
| Recipient address | `TEMPO_RECIPIENT` | `0x1111111111111111111111111111111111111111` |
| Transfer amount | `TEMPO_AMOUNT` | `0.17` |
| Token decimals | `TEMPO_DECIMALS` | `6` |
| Transfer memo | `TEMPO_MEMO` | `TEMPO-EVAL-001` |

<!-- tempobench_sync -->

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run example`
