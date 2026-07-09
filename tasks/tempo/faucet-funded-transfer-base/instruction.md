<!-- AUTO-GENERATED FROM tasks/tempo/_templates/faucet-funded-transfer/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Faucet Funded Transfer

Build a minimal TypeScript project that funds a sender wallet with Tempo's faucet, then sends an AlphaUSD transfer from that funded wallet.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| RPC URL | `TEMPO_RPC_URL` | `http://tempo-localnet:8545` |
| Token address | `TEMPO_TOKEN` | `0x20c0000000000000000000000000000000000001` |
| Recipient address | `TEMPO_RECIPIENT` | `0x1111111111111111111111111111111111111111` |
| Transfer amount | `TEMPO_AMOUNT` | `0.23` |
| Token decimals | `TEMPO_DECIMALS` | `6` |
| Sender wallet private key (fund this wallet via the faucet) | `TEMPO_FAUCET_PRIVATE_KEY` | provided |

## Execution Constraints

- `TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).
- Use that localnet RPC endpoint for all eval and self-check commands.
- Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.
- Do not run live testnet smoke tests; local eval checks must use the provided environment variables.

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run eval`
