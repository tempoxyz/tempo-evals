# Privy Server Wallet Send Transaction

## Overview

This task challenges agents to send a Tempo testnet stablecoin payment whose
payer is a Privy Ethereum server wallet, combining the Privy Node SDK's viem
integration with `viem/tempo`.

## What the Task Tests

- Bridging a Privy server wallet into a viem account (`@privy-io/node/viem`)
- Faucet funding and TIP-20 transfer execution on Tempo testnet
- Reading task parameters from the environment and reporting onchain evidence

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Usage of proper Tempo libraries: `viem/tempo`; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- The reported payer is a wallet in the Privy app, checked against the Privy API.
- Correctness of the transfer onchain: a Transfer event from the Privy wallet to the requested recipient for the requested amount.
