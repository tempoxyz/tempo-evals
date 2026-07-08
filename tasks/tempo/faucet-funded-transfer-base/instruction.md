# Tempo Faucet Funded Transfer

Build a minimal TypeScript project in `/app` that funds a wallet with Tempo's
faucet, then sends an AlphaUSD transfer from that funded wallet.

Use environment variables for all values:

- `TEMPO_RPC_URL`
- `TEMPO_FAUCET_PRIVATE_KEY`
- `TEMPO_TOKEN`
- `TEMPO_RECIPIENT`
- `TEMPO_AMOUNT`
- `TEMPO_DECIMALS`

<!-- tempobench_sync:begin -->
## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all build, run, and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local build/run checks must use the provided environment variables.
<!-- tempobench_sync:end -->

Requirements:

- Put the submission directly in `/app`.
- Include `package.json`.
- Include `tsconfig.json`.
- Put the runtime source in `src/index.ts`.
- Include scripts named exactly `build` and `run`.
- `npm run build` must typecheck or compile.
- `npm run run` must call the Tempo faucet for the faucet wallet before transfer.
- Transfer `TEMPO_AMOUNT` of `TEMPO_TOKEN` to `TEMPO_RECIPIENT`.
- Do not edit `/tests`, `/logs`, or `/solution`.
