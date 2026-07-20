# Claude Sonnet 5 paired MCP run — 2026-07-15

## Overview

Pass@1 with Sonnet against the authenticated Tempo MCP endpoint to compare Code
mode with direct MCP results. Each profile ran with two concurrent trials.

| Field | Value |
| --- | --- |
| Benchmark | `tempo/tempo-mcp-bench-v1` |
| Git revision | `5aec4a82b1e58aab73c6013a9064973113599257` |
| Base image | `ghcr.io/tempoxyz/stable-bench-base:source-c9e1d15eba6e8bad` |
| Profiles | `mcp-direct` and `mcp-code` |
| Attempts | 1 per task |
| Model | `claude-code / claude-sonnet-5` |
| Status | completed |
| Harbor Hub jobs | [direct](https://hub.harborframework.com/jobs/006934a5-26b4-4798-bf99-a154bb4e95c6), [code](https://hub.harborframework.com/jobs/a5af2950-2f9c-4a6d-ba39-4c09ff07e65a) |

## Results

| Metric | MCP direct | MCP code | Code delta |
| --- | ---: | ---: | ---: |
| Deterministic score | 0.800 | 0.900 | +0.100 (+12.5%) |
| Mean quality | 0.308 | 0.431 | +0.122 (+39.6%) |
| Strict valid answers | 4/12 | 6/12 | +2 |
| Input tokens | 13.94M | 9.80M | -4.14M (-29.7%) |
| Cache tokens | 13.16M | 9.01M | -4.15M (-31.5%) |
| Output tokens | 191,830 | 175,745 | -16,085 (-8.4%) |
| Model turns | 273 | 270 | -3 (-1.1%) |
| MCP calls | 261 | 222 | -39 (-14.9%) |
| MCP latency | 292.0s | 334.1s | +42.0s (+14.4%) |
| Cost | $7.69 | $8.30 | +$0.61 (+8.0%) |
