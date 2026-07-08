# Tempo Transfer With Memo

Build a minimal TypeScript project in `/app` that sends a Tempo localnet
stablecoin payment with a memo.

Use the following values:

- RPC URL: read from `TEMPO_RPC_URL`
- Payer private key: read from `TEMPO_PAYER_PRIVATE_KEY`
- Token address: read from `TEMPO_TOKEN`
- Recipient address: read from `TEMPO_RECIPIENT`
- Amount: read from `TEMPO_AMOUNT`
- Decimals: read from `TEMPO_DECIMALS`
- Memo: read from `TEMPO_MEMO`


## Tempo Access Profile

Tempo docs are available through the local docs service at `TEMPO_DOCS_URL` (http://tempo-docs:3000/developers). Use those docs for Tempo-specific APIs and examples. Do not use WebSearch, WebFetch, public docs sites, or public RPC endpoints.

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
- `npm run run` must execute the transfer on Tempo localnet.
- Attach the memo to the payment using `transferWithMemo`.
- Do not edit `/tests`, `/logs`, or `/solution`.
