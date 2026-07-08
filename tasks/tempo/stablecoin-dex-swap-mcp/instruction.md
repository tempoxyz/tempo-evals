<!-- AUTO-GENERATED FROM tasks/tempo/_templates/stablecoin-dex-swap/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Stablecoin DEX Swap

Build a minimal TypeScript project that uses Tempo's Stablecoin DEX to execute a swap.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| RPC URL | `TEMPO_RPC_URL` | `http://tempo-localnet:8545` |
| Taker private key | `TEMPO_PAYER_PRIVATE_KEY` | provided |
| DEX maker private key | `TEMPO_DEX_MAKER_PRIVATE_KEY` | provided |
| Stablecoin DEX address | `TEMPO_STABLECOIN_DEX` | `0xdec0000000000000000000000000000000000000` |
| Swap token in | `TEMPO_SWAP_TOKEN_IN` | `0x20c0000000000000000000000000000000000000` |
| Swap token out | `TEMPO_SWAP_TOKEN_OUT` | `0x20c0000000000000000000000000000000000001` |
| Swap amount in | `TEMPO_SWAP_AMOUNT_IN` | `100` |
| Minimum amount out | `TEMPO_SWAP_MIN_AMOUNT_OUT` | `0` |
| Token decimals | `TEMPO_DECIMALS` | `6` |

## Tempo Access Profile

The official Tempo MCP server is configured as `tempo`. Use it if your agent runtime exposes MCP tools; do not use WebSearch, WebFetch, or public RPC endpoints.

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all example and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local example checks must use the provided environment variables.

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run example`
