# Tempo Create Stablecoin With Transfer Policy

## Overview

This task challenges agents to create a Tempo stablecoin, create a transfer
policy, and link the policy to the new token.

## What the Task Tests

- Stablecoin creation with agent-defined metadata
- TIP-403 transfer policy creation
- Policy-to-token assignment

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Usage of proper Tempo libraries: the project must depend on `viem` and import `viem/tempo`; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- Correctness of the script, including onchain evidence of the reported token, policy account update, and policy-to-token link.
