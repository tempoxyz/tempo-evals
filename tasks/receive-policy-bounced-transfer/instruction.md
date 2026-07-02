# Tempo Receive Policy Bounced Transfer

Build a minimal TypeScript project in `/app` that configures the recipient
account with a receive policy that blocks inbound transfers, then sends funds
to that recipient so the transfer is blocked and held by the receive policy
guard.

Use environment variables for all values:

- `TEMPO_RPC_URL`
- `TEMPO_PAYER_PRIVATE_KEY`
- `TEMPO_RECIPIENT_PRIVATE_KEY`
- `TEMPO_TOKEN`
- `TEMPO_RECIPIENT`
- `TEMPO_AMOUNT`
- `TEMPO_DECIMALS`
- `TEMPO_MEMO`
- `TEMPO_RECEIVE_POLICY_SENDER_POLICY_ID`
- `TEMPO_RECEIVE_POLICY_TOKEN_POLICY_ID`

## Tempo Access Profile

No Tempo docs URL or Tempo MCP server is provided for this profile. Do not use WebSearch, WebFetch, or external documentation; solve from the prompt, local package APIs, and local files only.

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
- `npm run run` must set the recipient receive policy before sending funds.
- Use the configured sender and token policy ids.
- Send the configured token amount to `TEMPO_RECIPIENT` after the policy is set.
- The transfer should be blocked by the receive policy, not manually reverted.
- Do not edit `/tests`, `/logs`, or `/solution`.
