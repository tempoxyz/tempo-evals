<!-- AUTO-GENERATED FROM tasks/tempo-v1/_templates/transfer-with-memo/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Transfer With Memo

Build a minimal TypeScript project that sends a Tempo stablecoin payment with a memo.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| Token address | `TEMPO_TOKEN` | `0x20c0000000000000000000000000000000000001` |
| Recipient address | `TEMPO_RECIPIENT` | `0x1111111111111111111111111111111111111111` |
| Transfer amount | `TEMPO_AMOUNT` | `0.17` |
| Token decimals | `TEMPO_DECIMALS` | `6` |
| Transfer memo | `TEMPO_MEMO` | `TEMPO-EVAL-001` |

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
* The script should be runnable by `npm run eval`.
