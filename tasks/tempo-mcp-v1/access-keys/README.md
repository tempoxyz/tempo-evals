# Access Keys

## Overview

Investigate live authorization and sponsorship activity through the injected MCP server.

## What the Task Tests

- Data and docs correlation
- Grounded, cited synthesis without overclaiming

## Required MCP Tools

- Data: `v1_transactions_get`, `v1_transactions_transactionHash_get`, or `v1_addresses_address_activities`
- Docs: `docs_search`/`docs_find_pages`/`docs_read_page` or `docs_code`

## Verification

- A valid /app/answer.json is produced.
- The active MCP arm calls both a data tool and a docs tool.
- The answer cites Tempo docs and MCP data tools.
