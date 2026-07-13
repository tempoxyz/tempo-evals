# Tempo Transfer With Memo

## Overview

This task challenges agents to send a Tempo stablecoin payment on testnet with
the required memo attached.

## What the Task Tests

- Stablecoin transfer execution on Tempo testnet
- Correct memo attachment
- Agent-owned payer setup with an on-chain output artifact

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Usage of proper Tempo libraries: the project must depend on `viem` and import `viem/tempo`; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- Correctness of the script, including a TransferWithMemo event with the reported payer, recipient, amount, and memo.
