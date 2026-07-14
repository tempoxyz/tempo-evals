# Tempo Access Key Transfer

## Overview

This task challenges agents to authorize an access key for a Tempo testnet
account and send a stablecoin payment signed by that key.

## What the Task Tests

- Tempo account and access-key creation
- On-chain access-key authorization
- TIP-20 transfer execution through the authorized access key

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Usage of proper Tempo libraries: the project must depend on `viem` and import `viem/tempo`, `viem/tempo/actions`, `viem/tempo/chains`, or `viem/tempo/zones`; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- Correctness of the script, including:
  - The reported payer authorizes the reported access key.
  - The reported access key signs the transfer transaction for the payer.
  - The transfer sends the configured token amount to the configured recipient.
