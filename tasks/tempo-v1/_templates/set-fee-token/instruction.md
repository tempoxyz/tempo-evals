# Tempo Set Fee Token

Build a minimal TypeScript project that sets the account's default Tempo fee token to BetaUSD.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| RPC URL | `TEMPO_RPC_URL` | `http://tempo-localnet:8545` |
| Payer private key | `TEMPO_PAYER_PRIVATE_KEY` | provided |
| Fee token to set | `TEMPO_FEE_TOKEN` | `0x20c0000000000000000000000000000000000002` |

<!-- tempobench_sync -->

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run eval`
