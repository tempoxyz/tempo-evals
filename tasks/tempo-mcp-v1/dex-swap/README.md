# Dex Swap

## Overview

Investigate live Fee AMM liquidity through the injected MCP server.

## What the Task Tests

- Fee AMM pool comparison
- Grounded explanation of observed fee-token support

## Required MCP Tools

- Data: `v1_fee-amm_pools` and optionally `v1_fee-amm_mints`
- Docs: `docs_search`/`docs_find_pages`/`docs_read_page` or `docs_code`

## Verification

- A valid /app/answer.json is produced.
- The active MCP arm calls both a data tool and a docs tool.
- The answer cites Tempo docs and MCP data tools.
