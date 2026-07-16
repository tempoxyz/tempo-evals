# Tempo v1 paired production run — 2026-07-16

## Overview

Pass@3 across the nine Tempo v1 tasks to compare docs-only and Docs-plus-MCP
results across the eight shared production models.

| Field | Value |
| --- | --- |
| Benchmark | `tempo/tempo-bench-v1` |
| Git revisions | docs `d6384eb41c10ccf5e3d57eed6db6dbe29999898e`; MCP `45d044ef548731926fed76efe17895bb93ecbde7` |
| Tempo docs revision | `24479d5336b6c55ae299b3b5bead4b9d7f096ae5` |
| Profiles | `docs` and `mcp` |
| Attempts | 3 per task and model |
| Models | 8 shared models |
| Status | completed |
| Harbor Hub jobs | [docs](https://hub.harborframework.com/jobs/a1db301d-af4b-4fe7-9976-bd7e98939d66), [MCP](https://hub.harborframework.com/jobs/dac00a5f-56f9-45e8-a8be-f3425e0ae4eb) |

## Results

| Metric | Docs | MCP | MCP delta |
| --- | ---: | ---: | ---: |
| Pass rate | 193/216 (89.4%) | 198/216 (91.7%) | +2.3 pp |
| Mean reward | 0.831 | 0.855 | +0.024 (+2.9%) |
| Cost | $218.66 | $196.72 | -$21.95 (-10.0%) |

| Agent / model | Docs pass | MCP pass | Pass delta | Docs reward | MCP reward | Reward delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `claude-code / claude-fable-5` | 100.0% | 100.0% | 0.0 pp | 0.951 | 0.979 | +0.029 |
| `claude-code / claude-opus-4-8` | 96.3% | 96.3% | 0.0 pp | 0.892 | 0.926 | +0.034 |
| `claude-code / claude-haiku-4-5-20251001` | 25.9% | 44.4% | +18.5 pp | 0.206 | 0.330 | +0.124 |
| `claude-code / claude-sonnet-5` | 100.0% | 100.0% | 0.0 pp | 0.886 | 0.904 | +0.018 |
| `codex / gpt-5.4-mini-2026-03-17` | 100.0% | 96.3% | -3.7 pp | 0.903 | 0.869 | -0.034 |
| `codex / gpt-5.6-sol` | 100.0% | 96.3% | -3.7 pp | 0.974 | 0.934 | -0.040 |
| `codex / gpt-5.6-terra` | 100.0% | 100.0% | 0.0 pp | 0.969 | 0.965 | -0.004 |
| `codex / gpt-5.6-luna` | 92.6% | 100.0% | +7.4 pp | 0.865 | 0.930 | +0.065 |
