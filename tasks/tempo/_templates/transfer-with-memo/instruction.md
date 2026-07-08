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

<!-- tempobench_sync -->

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
