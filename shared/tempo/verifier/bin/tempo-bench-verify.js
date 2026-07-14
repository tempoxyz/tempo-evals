#!/usr/bin/env node
// SYNCED FROM shared/tempo/verifier/bin/tempo-bench-verify.js BY npm run sync. DO NOT EDIT COPIES IN tasks/.
require("../src/rpc-retry").installRpcRetry();
const { main } = require("../src/index");

main().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exitCode = 1;
});
