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

<!-- tempobench_sync:begin -->
## Tempo Access Profile

The official Tempo MCP server is configured as `tempo`. Use it if your agent runtime exposes MCP tools; do not use WebSearch, WebFetch, or public RPC endpoints.

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
- `npm run run` must execute the transfer on Tempo localnet.
- Use `transferWithMemo` semantics and include the memo.
- Use the fee payer private key as the Tempo transaction fee payer.
- Do not edit `/tests`, `/logs`, or `/solution`.
