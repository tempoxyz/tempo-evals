# Tempo MCP Efficiency Suite

Dataset: `tempo/tempo-mcp-bench-v1`

## Overview

This suite compares two ways of investigating live Tempo data: direct use of
Tempo documentation tools and programmatic documentation access through
`docs_code`. Each task requires a grounded answer that joins current MCP data
with protocol documentation.

## What It Measures

- Finding and interpreting live Tempo transactions, balances, tokens, pools,
  activities, and transfers through the Tempo API MCP server.
- Retrieving relevant protocol documentation through either direct tools or
  `docs_code`.
- Producing a concise, evidence-backed answer without treating live chain data
  as a fixed fixture.
- Using data and documentation tools efficiently while preserving provenance.

## Harness

Tasks write `/app/answer.json` rather than submitting a transaction. EvalKit
compiles the shared MCP bridge, compose configuration, and evaluator into every
canonical task during `npm run sync`. The direct and code bridges write their
tool calls to separate JSONL trace files. Agents use Tempo's native progressive
tool discovery; the bridge filters the underlying tools for each arm.

The paired profiles receive the same read-only Tempo data API:

| Profile | Documentation capability |
| --- | --- |
| `mcp-direct` | `docs_search`, `docs_find_pages`, and `docs_read_page` |
| `mcp-code` | `docs_code` |

Both arms receive one shared pair ID. The evaluator checks the answer structure,
required data and documentation calls, and cited claim evidence. RewardKit then
assesses answer quality. Trace artifacts make the observed tool use available to
the separate verifier after the agent environment and its MCP sidecars stop. The
verifier reads the restored files directly instead of contacting those services.

## Running the Suite

```bash
# Run the paired direct and code arms locally.
npm run bench:local:mcp -- --task-suite tempo-mcp

# Run one investigation with the generic development runner.
npm run bench:local:agent:dev -- --task-suite tempo-mcp --profile mcp-both \
  --task-filter access-keys

# Refresh this suite's manifest after task changes.
npm run dataset -- --tasks tasks/tempo-mcp-v1
```

Export both paired arms before using `npm run results:compare`; unmatched pair
IDs are rejected. Set `TEMPO_MCP_EVAL_URL` only when a non-default upstream MCP
endpoint is required.

## Implementation Notes

Live data changes. Do not encode frozen chain snapshots or assume a particular
transaction remains available. Grade the grounding and provenance of the
reported answer instead.

Task directories own their prompts, expected-answer requirements, and metadata.
EvalKit writes their Dockerfiles, oracle runtime, bridge, and shared verifier
assets from `config/tasks.yaml`, `shared/tempo/mcp-bridge`, and
`shared/tempo/mcp-eval`. Make shared harness changes there and run
`npm run sync`; do not hand-edit the compiled task copies.
