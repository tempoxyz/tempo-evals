# Fee Token Configuration

## Overview

Investigate a live non-default fee-token transaction through the injected MCP server.

## What the Task Tests

- Transaction and pool comparison
- Grounded fee-token configuration explanation

## Required MCP Tools

- Data: `v1_transactions_get`, `v1_transactions_transactionHash_get`, and `v1_fee-amm_pools`
- Docs: `docs_search`/`docs_find_pages`/`docs_read_page` or `docs_code`

## Verification

- A valid /app/answer.json is produced.
- The active MCP arm calls both a data tool and a docs tool.
- The answer cites Tempo docs and maps claim evidence to MCP data tools it used.
