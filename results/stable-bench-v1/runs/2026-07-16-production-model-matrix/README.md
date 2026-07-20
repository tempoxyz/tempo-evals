# Stable Bench production model matrix — 2026-07-16

## Overview

Comparison of eight Claude and GPT models across `stable-bench` to establish an
initial offline baseline.

Each suite ran pass@3 over a suite of nine tasks, with either access to Tempo docs (docs) or Tempo docs + an MCP (MCP).

| Field | Docs | MCP |
| --- | ---: | ---: |
| Benchmark | `tempo/stable-bench-v1` | `tempo/stable-bench-v1` |
| Harbor Hub job | [a1db301d](https://hub.harborframework.com/jobs/a1db301d-af4b-4fe7-9976-bd7e98939d66) | [dac00a5f](https://hub.harborframework.com/jobs/dac00a5f-56f9-45e8-a8be-f3425e0ae4eb) |
| Git revision | `45d044ef548731926fed76efe17895bb93ecbde7` | `45d044ef548731926fed76efe17895bb93ecbde7` |
| Trials | 216 | 216 |
| Aggregate mean score | 0.894 | 0.917 |
| Total cost | $218.66 | $196.72 |
| Total tokens | 358.99M | 374.19M |
| Total model turns | 6,117 | 5,948 |

## Aggregate results

| Family | Model | Docs score | MCP score | Docs cost | MCP cost | Docs tokens | MCP tokens |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Claude | Fable 5 | 1.000 | 1.000 | $51.97 | $49.70 | 24.12M | 25.39M |
| Claude | Haiku 4.5 | 0.259 | 0.444 | $12.05 | $9.77 | 29.89M | 56.83M |
| Claude | Opus 4.8 | 0.963 | 0.963 | $41.39 | $37.35 | 37.22M | 36.99M |
| Claude | Sonnet 5 | 1.000 | 1.000 | $47.97 | $37.10 | 79.91M | 80.65M |
| GPT | 5.4 mini | 1.000 | 0.963 | $14.54 | $13.95 | 81.85M | 79.03M |
| GPT | 5.6 Luna | 0.926 | 1.000 | $7.52 | $6.43 | 41.87M | 34.58M |
| GPT | 5.6 Sol | 1.000 | 0.963 | $27.53 | $27.86 | 30.01M | 30.25M |
| GPT | 5.6 Terra | 1.000 | 1.000 | $15.71 | $14.57 | 34.12M | 30.46M |

## Score vs. cost

![Stable Bench score versus cost](score-vs-cost.svg)

## Score vs. tokens

![Stable Bench score versus tokens](score-vs-tokens.svg)

## Score vs. turns

![Stable Bench score versus turns](score-vs-turns.svg)

## Analysis

- As of date, frontier models are able to consistently score high marks on stable-bench, nearly saturating the benchmark.
- Haiku and other smaller models perform very poorly, which we suspect is from:
  - Earlier knowledge cutoffs (Tempo docs were published in Jan 2026)
  - Observed reluctance to use web-search tools
- Usage of the MCP completes five more correct trials (198 vs. 193), raising mean score by
  2.3pp while lowering aggregate cost 10.0%.
- Tokens and turns are not predictive of correctness: Haiku/MCP uses 90.1%
  more tokens to improve, while Luna/MCP uses 17.4% fewer tokens to improve.
- Outside of Claude Fable, GPT models perform much stronger on all axis and ar marketly better on cost.

## Notes

`summary.csv` contains the chart inputs. Stable Bench score is mean
deterministic correctness. Tokens are input plus output tokens, so cached input
tokens are included once. Model turns are agent trajectory steps. Costs, tokens,
and turns are sums across all 27 trials for each model and access mode.

Regenerate all charts with:

```bash
python3 generate_charts.py --input summary.csv --config chart_config.json --out-dir .
```
