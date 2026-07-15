# Tempo Receive Policy Held Transfer

## Overview

This task challenges agents to configure a fresh recipient with a reject-all
receive policy and send a stablecoin transfer that the policy blocks and holds.

## What the Task Tests

- Fresh payer and recipient setup
- TIP-1028 receive-policy configuration
- TIP-20 block-and-hold behavior

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Usage of proper Tempo libraries: the project must depend on `viem` and import `viem/tempo`, `viem/tempo/actions`, `viem/tempo/chains`, or `viem/tempo/zones`; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- Correctness of the script, including the required policy, transaction order,
  blocked transfer, and exact balance held by the receive-policy guard.
