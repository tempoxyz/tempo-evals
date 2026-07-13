# Tempo Set Fee Token

## Overview

This task challenges agents to configure an account's default Tempo fee token
through the Fee Manager.

## What the Task Tests

- Fee Manager contract interaction
- Account fee token configuration
- Correct fee token argument selection

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Usage of proper Tempo libraries: the project must depend on `viem` and import `viem/tempo`; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- Correctness of the script, including onchain confirmation that the reported payer's default fee token matches the configured token.
