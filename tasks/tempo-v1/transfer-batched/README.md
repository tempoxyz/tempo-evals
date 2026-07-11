# Tempo Batched Transfer

## Overview

Build a TypeScript integration that pays every recipient in a supplied list the same TIP-20 stablecoin amount through one Tempo testnet batch transaction.

## What the Task Tests

- Encoding TIP-20 transfer calldata with `viem/tempo`.
- Submitting native Tempo transaction calls atomically from a TypeScript script.
- Reading dynamic recipient and payment configuration from the environment.

## Verification

- General file structure: `/app/package.json` and `/app/src/index.ts` are checked.
- Usage of proper Tempo libraries: `viem/tempo` TIP-20 ABI utilities are required; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- Correctness of the script, including:
  - Every configured recipient receives the configured stablecoin amount.
  - All transfers originate from the reported payer.
  - One native transaction contains a TIP-20 transfer call for every recipient.
