<!-- AUTO-GENERATED FROM tasks/tempo-v1/_templates/transfer-with-memo-fee-payer/README.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Transfer With Memo And Fee Payer

## Overview

This task challenges agents to send a Tempo stablecoin payment with a memo while
delegating transaction fees to a separate fee payer.

## What the Task Tests

- Memo-bearing stablecoin transfer execution
- Separate fee payer transaction handling
- Handling distinct payer and fee payer credentials

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Usage of proper Tempo libraries: `viem/tempo` `Actions.token.transfer`; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- Correctness of the script, including a memo transfer with the configured amount and a sponsored Tempo envelope for the expected fee payer and fee token.
