<!-- AUTO-GENERATED FROM tasks/tempo-v1/_templates/transfer-with-memo/README.md BY npm run sync. DO NOT EDIT MANUALLY. -->

# Tempo Transfer With Memo

## Overview

This task challenges agents to send a Tempo stablecoin payment on localnet with
the required memo attached.

## What the Task Tests

- Stablecoin transfer execution on Tempo localnet
- Correct memo attachment
- Using provided payment inputs without hardcoding fixture values

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Usage of proper Tempo libraries: `viem/tempo` `Actions.token.transfer`; other blockchain SDKs such as Solana, Sui, `ethers`, and `web3` are rejected.
- Correctness of the script, including a TransferWithMemo event with the configured payer, recipient, amount, and memo.
