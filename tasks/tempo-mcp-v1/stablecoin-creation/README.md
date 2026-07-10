# Stablecoin Creation

## Overview

Investigate live verified TIP-20 adoption and activity through the injected MCP server.

## What the Task Tests

- Token ranking and transaction inspection
- Grounded comparison with the TIP-20 specification

## Required MCP Tools

- Data: `v1_tokens_get` and `v1_tokens_token_transactions`
- Docs: `docs_search`/`docs_find_pages`/`docs_read_page` or `docs_code`

## Verification

- A valid /app/answer.json is produced.
- The active MCP arm calls both a data tool and a docs tool.
- The answer cites Tempo docs and MCP data tools.
