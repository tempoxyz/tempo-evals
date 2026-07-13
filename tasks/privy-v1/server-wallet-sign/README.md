# Privy Server Wallet Sign

## Overview

This task challenges agents to sign a verifier-supplied message with a Privy
Ethereum server wallet through the Privy Node SDK.

## What the Task Tests

- Privy server wallet creation and message signing via the wallet RPC API
- Reading the signing payload from the environment at runtime
- Producing a signature that cryptographically binds to the reported wallet

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- Offline signature recovery: the reported signature must recover to the reported wallet address for the per-run message.
- The reported wallet exists in the Privy app and owns the reported address.
