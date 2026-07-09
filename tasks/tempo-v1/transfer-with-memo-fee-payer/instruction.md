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
