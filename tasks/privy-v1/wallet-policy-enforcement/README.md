# Privy Wallet Policy Enforcement

## Overview

This task challenges agents to govern a Privy Ethereum server wallet with a
recipient-allowlist policy and demonstrate the policy is live: transactions to
the allowed recipient sign successfully while any other recipient is denied.

## What the Task Tests

- Creating Privy policies with `ethereum_transaction` conditions
- Attaching a policy to a server wallet at creation time
- Signing transactions through the Privy wallet API under policy constraints
- Reading task parameters from the environment and reporting verifiable evidence

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- The reported wallet exists in the Privy app with the reported policy attached.
- The reported signed transaction targets the allowed recipient and recovers to the wallet address.
- Live policy probes: the verifier asks Privy to sign a transaction to a random recipient (must be denied) and to the allowed recipient (must succeed).
