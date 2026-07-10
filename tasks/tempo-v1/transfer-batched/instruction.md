# Tempo Batched Transfer

Build a minimal TypeScript project that pays every configured recipient the same Tempo stablecoin amount in one transaction.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| Token address | `TEMPO_TOKEN` | `0x20c0000000000000000000000000000000000001` |
| Recipient addresses | `TEMPO_RECIPIENTS` | JSON array provided |
| Amount per recipient | `TEMPO_AMOUNT` | `0.01` |
| Token decimals | `TEMPO_DECIMALS` | `6` |

Use `Actions.token.transferSync` from `viem/tempo` with `tempoTestnet`, not a
generic ERC-20 client. Choose and report the payer; use the Tempo testnet
`Actions.faucet.fundSync` if it needs funds. Report the hash from the successful
transfer.

## Tempo Documentation

Tempo documentation is available publicly at https://docs.tempo.xyz. Use it for Tempo-specific APIs and examples.

## Execution Constraints

- Use the Tempo testnet.

## Output

When `npm run eval` finishes, write exactly one JSON file at `/app/out.json`
matching this schema:

```json
{
  "type": "object",
  "required": ["payer", "transferTransactionHash"],
  "additionalProperties": false,
  "properties": {
    "payer": {
      "type": "object",
      "required": ["address"],
      "additionalProperties": false,
      "properties": {
        "address": { "type": "string" }
      }
    },
    "transferTransactionHash": { "type": "string" }
  }
}
```

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* Use a native Tempo batch transaction: encode a TIP-20 `transfer` call for every recipient and submit them together through `calls`.
* The script should be runnable by `npm run eval`.
