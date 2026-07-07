<!-- AUTO-GENERATED FROM tasks/tempo/_templates/access-key-transfer/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Access Key Transfer

Build a minimal TypeScript project in `/app` that authorizes a Tempo access key
for the payer account, then uses that access key to submit a stablecoin payment
on Tempo localnet.

Use the following values:

- RPC URL: read from `TEMPO_RPC_URL`
- Payer private key: read from `TEMPO_PAYER_PRIVATE_KEY`
- Token address: read from `TEMPO_TOKEN`
- Recipient address: read from `TEMPO_RECIPIENT`
- Amount: read from `TEMPO_AMOUNT`
- Decimals: read from `TEMPO_DECIMALS`

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all build, run, and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local build/run checks must use the provided environment variables.

Requirements:

- Put the submission directly in `/app`.
- Include a `package.json`.
- Include `tsconfig.json`.
- Put the runtime source in `src/index.ts`.
- Include scripts named exactly `build` and `run`.
- `npm run build` must typecheck or compile the project.
- `npm run run` must authorize the access key for the payer account, then submit the transfer using the access key account.
- Fund the payer on localnet if needed before authorizing the access key.
- Do not edit `/tests`, `/logs`, or `/solution`.
