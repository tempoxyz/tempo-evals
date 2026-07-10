# Tempo Transfer With Memo And Fee Payer

Build a minimal TypeScript project that sends a Tempo stablecoin payment with a memo and a separate fee payer.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| Token address | `TEMPO_TOKEN` | `0x20c0000000000000000000000000000000000001` |
| Recipient address | `TEMPO_RECIPIENT` | `0x1111111111111111111111111111111111111111` |
| Transfer amount | `TEMPO_AMOUNT` | `0.19` |
| Token decimals | `TEMPO_DECIMALS` | `6` |
| Transfer memo | `TEMPO_MEMO` | `TEMPO-FEEPAYER-001` |
| Fee token | `TEMPO_FEE_TOKEN` | `0x20c0000000000000000000000000000000000001` |

Use `Actions.token.transferSync` from `viem/tempo` with `tempoTestnet`.
Generic ERC-20 and RPC fallbacks do not satisfy this task. No private-key
environment variables are provided: create and report both accounts, then use
`Actions.faucet.fundSync` if either needs funds. Convert the amount with
`parseUnits` and `TEMPO_DECIMALS`. Only write
`/app/out.json` after the `Actions.token.transferSync` call succeeds.

## Tempo Documentation

Tempo documentation is available publicly at https://docs.tempo.xyz. Use it for Tempo-specific APIs and examples.

## Execution Constraints

- Use the Tempo testnet.

## Output

When `npm run eval` finishes, write `/app/out.json` matching this schema:

```json
{
  "type": "object",
  "required": ["payer", "feePayer", "transferTransactionHash"],
  "additionalProperties": false,
  "properties": {
    "payer": { "type": "object", "required": ["address"], "additionalProperties": false, "properties": { "address": { "type": "string" } } },
    "feePayer": { "type": "object", "required": ["address"], "additionalProperties": false, "properties": { "address": { "type": "string" } } },
    "transferTransactionHash": { "type": "string" }
  }
}
```

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run eval`.
