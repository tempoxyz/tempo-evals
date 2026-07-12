# Transaction Status

## Overview

Investigate a historical block and upgrade state through the injected MCP server.

## What the Task Tests

- Block, transaction, and transfer inspection
- Grounded upgrade-state determination

## Required MCP Tools

- Data: `v1_blocks_block`, `v1_transactions_get`, and `v1_transfers`
- Docs: `docs_search`/`docs_find_pages`/`docs_read_page` or `docs_code`

## Verification

- A valid `/app/answer.json` is produced.
- The active MCP arm calls both a data tool and a docs tool.
- The answer cites Tempo docs and maps claim evidence to MCP data tools it used.
