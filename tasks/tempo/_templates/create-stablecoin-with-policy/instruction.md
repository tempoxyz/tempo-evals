# Tempo Create Stablecoin With Transfer Policy

Build a minimal TypeScript project that creates a TIP-20 stablecoin,
creates a Tempo transfer policy, and links that policy to the new token.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| RPC URL | `TEMPO_RPC_URL` | `http://tempo-localnet:8545` |
| Payer private key | `TEMPO_PAYER_PRIVATE_KEY` | provided |
| Fee token | `TEMPO_TOKEN` | `0x20c0000000000000000000000000000000000001` |
| Stablecoin name | `TEMPO_STABLECOIN_NAME` | `Tempo Bench Policy USD` |
| Stablecoin symbol | `TEMPO_STABLECOIN_SYMBOL` | `TBPUSD` |
| Stablecoin currency | `TEMPO_STABLECOIN_CURRENCY` | `USD` |
| Stablecoin salt | `TEMPO_STABLECOIN_SALT` | `0x0000000000000000000000000000000000000000000000000000000000000b01` |
| Policy type | `TEMPO_POLICY_TYPE` | `blacklist` |
| Policy account | `TEMPO_POLICY_ACCOUNT` | `0x1111111111111111111111111111111111111111` |

<!-- tempobench_sync -->

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run eval`
