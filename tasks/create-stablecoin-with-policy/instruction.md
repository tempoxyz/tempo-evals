# Tempo Create Stablecoin With Transfer Policy

Build a minimal TypeScript project in `/app` that creates a TIP-20 stablecoin,
creates a TIP-403 transfer policy, and links that policy to the new token.

Use environment variables for all values:

- `TEMPO_RPC_URL`
- `TEMPO_PAYER_PRIVATE_KEY`
- `TEMPO_TOKEN`
- `TEMPO_STABLECOIN_NAME`
- `TEMPO_STABLECOIN_SYMBOL`
- `TEMPO_STABLECOIN_CURRENCY`
- `TEMPO_STABLECOIN_SALT`
- `TEMPO_POLICY_TYPE`
- `TEMPO_POLICY_ACCOUNT`

Requirements:

- Put the submission directly in `/app`.
- Include `package.json`.
- Include `tsconfig.json`.
- Put the runtime source in `src/index.ts`.
- Include scripts named exactly `build` and `run`.
- `npm run build` must typecheck or compile.
- Create the stablecoin with currency `TEMPO_STABLECOIN_CURRENCY`.
- Create a TIP-403 policy of type `TEMPO_POLICY_TYPE` including `TEMPO_POLICY_ACCOUNT`.
- Link the created policy to the created stablecoin.
- Do not edit `/tests`, `/logs`, or `/solution`.
