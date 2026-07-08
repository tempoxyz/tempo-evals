# Tempo Transfer With Memo And Fee Payer

Build a minimal TypeScript project in `/app` that sends a Tempo localnet
stablecoin payment with a 32-byte memo and a separate fee payer.

Use environment variables for all values:

- `TEMPO_RPC_URL`
- `TEMPO_PAYER_PRIVATE_KEY`
- `TEMPO_FEE_PAYER_PRIVATE_KEY`
- `TEMPO_FEE_TOKEN`
- `TEMPO_TOKEN`
- `TEMPO_RECIPIENT`
- `TEMPO_AMOUNT`
- `TEMPO_DECIMALS`
- `TEMPO_MEMO`

<!-- tempobench_sync -->

Requirements:

- Put the submission directly in `/app`.
- Include `package.json`.
- Include `tsconfig.json`.
- Put the runtime source in `src/index.ts`.
- Include scripts named exactly `build` and `run`.
- `npm run build` must typecheck or compile.
- `npm run run` must execute the transfer on Tempo localnet.
- Use `transferWithMemo` semantics and include the memo.
- Use the fee payer private key as the Tempo transaction fee payer.
- Do not edit `/tests`, `/logs`, or `/solution`.
