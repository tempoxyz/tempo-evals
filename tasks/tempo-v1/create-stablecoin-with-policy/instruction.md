# Tempo Create Stablecoin With Transfer Policy

Build a minimal TypeScript project that creates a TIP-20 stablecoin,
creates a Tempo transfer policy of type `TEMPO_POLICY_TYPE` that covers
`TEMPO_POLICY_ACCOUNT` (a blacklist policy must restrict that account),
and links that policy to the new token.

## Parameters

| Value | Env variable | Default |
| --- | --- | --- |
| Fee token | `TEMPO_TOKEN` | `0x20c0000000000000000000000000000000000001` |
| Stablecoin currency | `TEMPO_STABLECOIN_CURRENCY` | `USD` |
| Policy type | `TEMPO_POLICY_TYPE` | `blacklist` |
| Policy account | `TEMPO_POLICY_ACCOUNT` | `0x1111111111111111111111111111111111111111` |

## Tempo Documentation

Tempo documentation is available at https://docs.tempo.xyz.

## Execution Constraints

- Use the Tempo testnet.

## Output

When `npm run eval` finishes, write `/app/out.json` matching this schema:

```json
{
  "type": "object",
  "required": ["payer", "stablecoin", "policy", "tokenCreateTransactionHash", "policyCreateTransactionHash", "policyAccountTransactionHash", "linkPolicyTransactionHash"],
  "additionalProperties": false,
  "properties": {
    "payer": { "type": "object", "required": ["address"], "additionalProperties": false, "properties": { "address": { "type": "string" } } },
    "stablecoin": { "type": "object", "required": ["address", "name", "symbol", "currency", "salt"], "additionalProperties": false, "properties": { "address": { "type": "string" }, "name": { "type": "string" }, "symbol": { "type": "string" }, "currency": { "type": "string" }, "salt": { "type": "string" } } },
    "policy": { "type": "object", "required": ["id"], "additionalProperties": false, "properties": { "id": { "type": "string" } } },
    "tokenCreateTransactionHash": { "type": "string" },
    "policyCreateTransactionHash": { "type": "string" },
    "policyAccountTransactionHash": { "type": "string" },
    "linkPolicyTransactionHash": { "type": "string" }
  }
}
```

Requirements:

* Put the submission directly in `/app`.
* Put the runtime source in `src/index.ts`.
* The script should be runnable by `npm run eval`.
