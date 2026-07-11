# Passkey Account

## Overview

Investigate live account-authorized activity through the injected MCP server.

## What the Task Tests

- Activity inspection and careful inference
- Grounded passkey-account explanation

## Required MCP Tools

- Data: `v1_addresses_address_activities` or `v1_transactions_transactionHash_activities`
- Docs: `docs_search`/`docs_find_pages`/`docs_read_page` or `docs_code`

## Verification

- A valid /app/answer.json is produced.
- The active MCP arm calls both a data tool and a docs tool.
- The answer cites Tempo docs and maps claim evidence to MCP data tools it used.
