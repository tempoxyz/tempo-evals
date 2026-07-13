# Claude Sonnet 5 paired MCP run — 2026-07-12

## Overview

Pass@1 with sonnet to establish baseline for Code mode vs. direct MCP results.

| Field | Value |
| --- | --- |
| Benchmark | `tempo/tempo-mcp-bench-v1` |
| Git revision | `e9ebffd0d823ab2af3aac298330cb033022351c2` |
| Base image | `ghcr.io/tempoxyz/tempo-bench-base@sha256:f5de8cee38a434c090c67e3e94bf340c7595070b5866812e843470ac65e40073` |
| Profiles | `mcp-direct` and `mcp-code` |
| Attempts | 1 per task |
| Model | `claude-code / claude-sonnet-5` |
| Status | completed |
| Harbor Hub jobs | [direct](https://hub.harborframework.com/jobs/d5efdf21-91de-43c3-87f8-2a0127d5ae00), [code](https://hub.harborframework.com/jobs/16c5acaf-b03d-4495-8781-9e076a9f47f4) |

## Results

| Metric | MCP direct | MCP code | Code delta |
| --- | ---: | ---: | ---: |
| Deterministic score | 1.000 | 1.000 | 0.000 |
| Mean quality | 0.826 | 0.840 | +0.014 (+1.7%) |
| Strict valid answers | 12/12 | 12/12 | 0 |
| Input tokens | 23.16M | 22.75M | -0.41M (-1.8%) |
| Cache tokens | 22.07M | 21.71M | -0.36M (-1.6%) |
| Output tokens | 214,911 | 203,950 | -10,961 (-5.1%) |
| Model turns | 372 | 323 | -49 (-13.2%) |
| MCP calls | 252 | 235 | -17 (-6.7%) |
| MCP latency | 462.7s | 405.9s | -56.7s (-12.3%) |
| Cost | $13.94 | $13.46 | -$0.48 (-3.4%) |

Both arms completed all tasks with full deterministic correctness. The code arm
was modestly more efficient in this single paired attempt; repeat the paired run
before drawing a stable access-mode conclusion.
