const assert = require("node:assert/strict");
const fs = require("node:fs");
const test = require("node:test");

test("npm install retains error output", () => {
  const source = fs.readFileSync(require.resolve("../src/index"), "utf8");
  assert.match(source, /\["install", "--loglevel=error"\]/);
  assert.doesNotMatch(source, /--silent/);
});
