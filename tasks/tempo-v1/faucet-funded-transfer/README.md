# Tempo Faucet Funded Transfer

## Overview

This task challenges agents to fund a wallet through Tempo's faucet and then
send a stablecoin transfer from that funded wallet.

## What the Task Tests

- Faucet funding before transfer
- Stablecoin transfer from a funded wallet
- On-chain evidence tying funding and transfer events

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Usage of proper Tempo libraries: `viem/tempo` `Actions.faucet.fund` and `Actions.token.transfer`; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- Correctness of the script, including onchain evidence that the faucet funded the reported payer before its configured transfer.
