<!-- AUTO-GENERATED FROM tasks/tempo/_templates/create-stablecoin-with-policy/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Create Stablecoin With Transfer Policy

Build a minimal TypeScript project that creates a TIP-20 stablecoin,
creates a Tempo transfer policy of type `TEMPO_POLICY_TYPE` that covers
`TEMPO_POLICY_ACCOUNT` (a blacklist policy must restrict that account),
and links that policy to the new token.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| RPC URL | `TEMPO_RPC_URL` | `http://tempo-localnet:8545` |
| Payer private key | `TEMPO_PAYER_PRIVATE_KEY` | provided |
| Fee token | `TEMPO_TOKEN` | `0x20c0000000000000000000000000000000000001` |
| Stablecoin name | `TEMPO_STABLECOIN_NAME` | `Tempo Bench Policy USD` |
| Stablecoin symbol | `TEMPO_STABLECOIN_SYMBOL` | `TBPUSD` |
| Stablecoin currency | `TEMPO_STABLECOIN_CURRENCY` | `USD` |
| Policy type | `TEMPO_POLICY_TYPE` | `blacklist` |
| Policy account | `TEMPO_POLICY_ACCOUNT` | `0x1111111111111111111111111111111111111111` |

## Tempo Access Profile

The official Tempo MCP server is configured as `tempo`. Use it if your agent runtime exposes MCP tools; do not use WebSearch, WebFetch, or public RPC endpoints.

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all eval and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local eval checks must use the provided environment variables.

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run eval`
