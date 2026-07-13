const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { assertVerifierDigest, verifierDigest } = require("../src/digest");

test("accepts the verifier fingerprint pinned by the task", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-digest-"));
  const expectedPath = path.join(directory, "expected.sha256");
  fs.writeFileSync(expectedPath, `${verifierDigest()}\n`);

  assert.doesNotThrow(() => assertVerifierDigest(expectedPath));
});

test("rejects a verifier that differs from the task fingerprint", () => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "tempo-verifier-digest-"));
  const expectedPath = path.join(directory, "expected.sha256");
  fs.writeFileSync(expectedPath, `sha256:${"0".repeat(64)}\n`);

  assert.throws(
    () => assertVerifierDigest(expectedPath),
    /baked Tempo verifier does not match the task digest/,
  );
});
