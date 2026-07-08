<!-- AUTO-GENERATED FROM sources/tempo/transfer-with-memo/instruction.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Transfer With Memo

Build a TypeScript app in `/app` that sends one transfer with memo transaction
on Tempo testnet.

Tempo is EVM-compatible. Use an Ethereum/EVM TypeScript client such as `viem`
or `ethers`; do not use Solana libraries.

Add npm scripts named `build` and `run`. `npm run build` must compile the
project. `npm run run` must execute the compiled JavaScript and send the
transaction.

Use the RPC URL from `TEMPO_RPC_URL`, payer private key from
`TEMPO_PAYER_PRIVATE_KEY`, token address from `TEMPO_TOKEN`, recipient address
from `TEMPO_RECIPIENT`, amount from `TEMPO_AMOUNT`, decimals from
`TEMPO_DECIMALS`, and memo from `TEMPO_MEMO`. Read these values at run time;
`npm run build` must not require them.

Use transfer with memo on the provided pathUSD token. Encode the memo as
`bytes32`.

## Tempo Access Profile

The official Tempo MCP server is configured as `tempo`. Use it if your agent runtime exposes MCP tools; do not use WebSearch, WebFetch.

When the run finishes, write exactly one JSON file at `/app/out.json` matching
this schema:

```json
{
  "type": "object",
  "required": ["transactionHash"],
  "additionalProperties": false,
  "properties": {
    "transactionHash": { "type": "string", "pattern": "^0x[0-9a-fA-F]{64}$" }
  }
}
```
