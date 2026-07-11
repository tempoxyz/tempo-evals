# Tip20 Transfer Memo

## Overview

Reconcile live account transfer activity through the injected MCP server.

## What the Task Tests

- Transfer, activity, and balance reasoning
- Grounded protocol-native activity explanation

## Required MCP Tools

- Data: `v1_addresses_address_balances`, `v1_addresses_address_activities`, and `v1_transfers`
- Docs: `docs_search`/`docs_find_pages`/`docs_read_page` or `docs_code`

## Verification

- A valid /app/answer.json is produced.
- The active MCP arm calls both a data tool and a docs tool.
- The answer cites Tempo docs and maps claim evidence to MCP data tools it used.
