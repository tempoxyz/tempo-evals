# Tempo Stablecoin DEX Swap

## Overview

This task challenges agents to execute a swap through Tempo's Stablecoin DEX
on testnet.

## What the Task Tests

- Token approval flow
- Stablecoin DEX swap execution
- Taker output artifact and on-chain fill evidence

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Usage of proper Tempo libraries: the project must depend on `viem` and import `viem/tempo`, `viem/tempo/actions`, `viem/tempo/chains`, or `viem/tempo/zones`; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- Correctness of the script, including an onchain DEX fill for the reported taker and configured input amount, with the configured input token spent in that transaction.
