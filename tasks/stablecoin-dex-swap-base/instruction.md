# Tempo Stablecoin DEX Swap

Build a minimal TypeScript project in `/app` that uses Tempo's Stablecoin DEX
to execute a swap.

Use environment variables for all values:

- `TEMPO_RPC_URL`
- `TEMPO_PAYER_PRIVATE_KEY`
- `TEMPO_DEX_MAKER_PRIVATE_KEY`
- `TEMPO_STABLECOIN_DEX`
- `TEMPO_SWAP_TOKEN_IN`
- `TEMPO_SWAP_TOKEN_OUT`
- `TEMPO_SWAP_AMOUNT_IN`
- `TEMPO_SWAP_MIN_AMOUNT_OUT`
- `TEMPO_DECIMALS`

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all build, run, and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local build/run checks must use the provided environment variables.

Requirements:

- Put the submission directly in `/app`.
- Include `package.json`.
- Include `tsconfig.json`.
- Put the runtime source in `src/index.ts`.
- Include scripts named exactly `build` and `run`.
- `npm run build` must typecheck or compile.
- `npm run run` must fund wallets as needed, approve DEX token spending, provide liquidity, and execute a DEX swap.
- Use Tempo Stablecoin DEX swap APIs, not a plain token transfer.
- Do not edit `/tests`, `/logs`, or `/solution`.
