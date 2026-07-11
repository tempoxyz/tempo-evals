# Fee Token And Payer

## Overview

Investigate a fixed transaction and its fee behavior through the injected MCP server.

## What the Task Tests

- Transaction, receipt, and activity inspection
- Grounded fee calculation and documentation comparison

## Required MCP Tools

- Data: `v1_transactions_transactionHash_get` and `v1_transactions_transactionHash_activities`
- Docs: `docs_search`/`docs_find_pages`/`docs_read_page` or `docs_code`

## Verification

- A valid /app/answer.json is produced.
- The active MCP arm calls both a data tool and a docs tool.
- The answer cites Tempo docs and maps claim evidence to MCP data tools it used.
