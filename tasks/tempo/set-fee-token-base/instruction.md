# Tempo Set Fee Token

Build a minimal TypeScript project in `/app` that sets the account's default
Tempo fee token to AlphaUSD.

Use environment variables for all values:

- `TEMPO_RPC_URL`
- `TEMPO_PAYER_PRIVATE_KEY`
- `TEMPO_FEE_TOKEN`
- `TEMPO_FEE_MANAGER`

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
- `npm run run` must call `setUserToken` on the Fee Manager.
- Use `TEMPO_FEE_TOKEN` as the token argument.
- Do not edit `/tests`, `/logs`, or `/solution`.
