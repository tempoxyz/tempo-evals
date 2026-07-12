# Claude Sonnet 4.5 MCP benchmark — 2026-07-12

| Field | Value |
| --- | --- |
| Benchmark | `tempo/tempo-mcp-bench-v1` |
| Dataset manifest | `tasks/tempo-mcp-v1/dataset.toml` |
| Git revision | `316f8820827b340bbf7eeba4c1d792080d44729a` |
| Base image | `ghcr.io/tempoxyz/tempo-bench-base@sha256:f5de8cee38a434c090c67e3e94bf340c7595070b5866812e843470ac65e40073` |
| Profiles | `mcp-direct` and `mcp-code` |
| Attempts | 3 per task |
| Models | `claude-code / claude-sonnet-4-5` |
| Status | completed |
| Harbor Hub jobs | [direct](https://hub.harborframework.com/jobs/e46d914e-eb28-42af-9995-e2a58b0351f3), [code](https://hub.harborframework.com/jobs/b7a5d93c-c242-416a-9205-07e0b8e65bd7) |

## Headline results

| Metric | MCP direct | MCP code |
| --- | ---: | ---: |
| Trials | 36 | 36 |
| Passed trials | 13 | 11 |
| Pass rate | 36.1% | 30.6% |
| Mean quality | 0.248 | 0.211 |
| Cost | $19.12 | $19.39 |
| Trial errors | 0 | 0 |

The direct arm recovered one transient retry. Both Harbor Hub jobs are private.
