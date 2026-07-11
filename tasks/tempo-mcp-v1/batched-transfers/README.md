# Batched Transfers

## Overview

Investigate a multi-payment flow through the injected MCP server.

## What the Task Tests

- Transaction and activity correlation
- Grounded, cited protocol mapping

## Required MCP Tools

- Data: `v1_transactions_get`, `v1_transactions_transactionHash_activities`, and `v1_transfers`
- Docs: `docs_search`/`docs_find_pages`/`docs_read_page` or `docs_code`

## Verification

- A valid /app/answer.json is produced.
- The active MCP arm calls both a data tool and a docs tool.
- The answer cites Tempo docs and maps claim evidence to MCP data tools it used.
