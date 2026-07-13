# Privy Server Wallet Create

## Overview

This task challenges agents to create a Privy Ethereum server wallet with the
Privy Node SDK and report its identity as an output artifact.

## What the Task Tests

- Privy Node SDK client setup from environment credentials
- Server wallet creation for the Ethereum chain type
- Producing a machine-checkable output artifact

## Verification

- General file structure: a runnable `/app` TypeScript project with `src/index.ts` and an `npm run eval` entry point.
- The reported wallet exists in the Privy app: the verifier fetches it from the Privy API and matches the address and chain type.
- The wallet was created during this evaluation, not reused from a previous run.
