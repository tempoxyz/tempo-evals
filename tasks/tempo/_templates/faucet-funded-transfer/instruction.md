# Tempo Faucet Funded Transfer

Build a minimal TypeScript project that funds a wallet with Tempo's faucet, then sends an AlphaUSD transfer from that funded wallet.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| RPC URL | `TEMPO_RPC_URL` | `http://tempo-localnet:8545` |
| Token address | `TEMPO_TOKEN` | `0x20c0000000000000000000000000000000000001` |
| Recipient address | `TEMPO_RECIPIENT` | `0x1111111111111111111111111111111111111111` |
| Transfer amount | `TEMPO_AMOUNT` | `0.23` |
| Token decimals | `TEMPO_DECIMALS` | `6` |
| Faucet wallet private key | `TEMPO_FAUCET_PRIVATE_KEY` | provided |

<!-- tempobench_sync -->

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run eval`
