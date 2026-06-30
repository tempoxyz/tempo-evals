#!/usr/bin/env node
const { main } = require("../src/index");

main().catch((error) => {
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exitCode = 1;
});
