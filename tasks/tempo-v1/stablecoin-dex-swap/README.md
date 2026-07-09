<!-- AUTO-GENERATED FROM tasks/tempo-v1/_templates/stablecoin-dex-swap/README.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Stablecoin DEX Swap

## Overview

This task challenges agents to execute a swap through Tempo's Stablecoin DEX
against liquidity that is already seeded on the localnet.

## What the Task Tests

- Token approval flow
- Stablecoin DEX swap execution

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Usage of proper Tempo libraries: `viem/tempo` `Actions.token.approve` and a Stablecoin DEX buy or sell action; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- Correctness of the script, including an onchain DEX fill for the configured taker and input amount, with the configured input token spent in that transaction.
