# Faucet Funding

## Overview

Investigate an account's live balances and recent activity through the injected MCP server.

## What the Task Tests

- Balance and activity correlation
- Grounded feature classification

## Required MCP Tools

- Data: `v1_addresses_address_balances` and `v1_addresses_address_activities`
- Docs: `docs_search`/`docs_find_pages`/`docs_read_page` or `docs_code`

## Verification

- A valid /app/answer.json is produced.
- The active MCP arm calls both a data tool and a docs tool.
- The answer cites Tempo docs and MCP data tools.
