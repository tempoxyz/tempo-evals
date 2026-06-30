# Tempo Access Key Transfer

Build a minimal TypeScript project in `/app` that authorizes a Tempo access key,
then uses that access key to send a localnet stablecoin payment with a memo.

Use environment variables for all values:

- `TEMPO_RPC_URL`
- `TEMPO_PAYER_PRIVATE_KEY`
- `TEMPO_ACCESS_KEY_PRIVATE_KEY`
- `TEMPO_TOKEN`
- `TEMPO_RECIPIENT`
- `TEMPO_AMOUNT`
- `TEMPO_ACCESS_KEY_LIMIT`
- `TEMPO_DECIMALS`
- `TEMPO_MEMO`



## Tempo Access Profile

Tempo docs are available at https://docs.tempo.xyz/ and through the `TEMPO_DOCS_URL` environment variable. You may use WebSearch/WebFetch for Tempo docs; prefer docs from docs.tempo.xyz and do not use public RPC endpoints.

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
- Create an access key from `TEMPO_ACCESS_KEY_PRIVATE_KEY` for the payer account.
- Authorize the access key on Tempo localnet.
- Configure the access key with `TEMPO_ACCESS_KEY_LIMIT` for `TEMPO_TOKEN`.
- Use the access key, not the payer key, to execute the memo transfer.
- Attach `TEMPO_MEMO` to the payment.
- Do not edit `/tests`, `/logs`, or `/solution`.
