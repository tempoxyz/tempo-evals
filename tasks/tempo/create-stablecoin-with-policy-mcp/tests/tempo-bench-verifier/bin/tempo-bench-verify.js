#!/usr/bin/env node
// AUTO-GENERATED FROM shared/verifier/bin/tempo-bench-verify.js BY npm run sync. DO NOT EDIT MANUALLY.
const { main } = require("../src/index");

main().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exitCode = 1;
});
