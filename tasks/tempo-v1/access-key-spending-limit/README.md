# Tempo Access Key Spending Limit

## Overview

This task challenges agents to authorize an access key for a Tempo testnet
account with a token-specific spending limit, send a stablecoin payment signed
by that key, and prove an attempted payment above the remaining limit reverts.

## What the Task Tests

- Tempo account and access-key creation
- On-chain access-key authorization with a token-specific spending limit
- TIP-20 transfer execution, remaining-limit reads, and on-chain limit enforcement

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Usage of proper Tempo libraries: `viem/tempo` access-key authorization, spending-limit reads, and token transfer actions are required; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- Correctness of the script, including:
  - The reported payer authorizes the reported access key with the configured token limit.
  - The reported access key signs the transfer transaction for the payer.
  - The transfer sends the configured token amount to the configured recipient.
  - The account keychain records the successful spend against the limit.
  - A second access-key transfer above the remaining allowance reverts with `SpendingLimitExceeded()`.
