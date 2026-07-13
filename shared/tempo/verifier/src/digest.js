const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const VERIFIER_ROOT = path.resolve(__dirname, "..");
const DIGEST_PATH = path.join(
  process.env.TEMPO_BENCH_TESTS_DIR || "/tests",
  "tempo-bench-verifier.sha256",
);

function filesUnder(root, relativePath) {
  const absolutePath = path.join(root, relativePath);
  return fs.readdirSync(absolutePath, { withFileTypes: true }).flatMap((entry) => {
    const child = path.posix.join(relativePath, entry.name);
    if (entry.isDirectory()) return filesUnder(root, child);
    return entry.isFile() ? [child] : [];
  });
}

function verifierDigest(root = VERIFIER_ROOT) {
  const files = [
    "package-lock.json",
    "package.json",
    ...filesUnder(root, "bin"),
    ...filesUnder(root, "src"),
  ].sort();
  const hash = crypto.createHash("sha256");
  for (const file of files) {
    hash.update(file);
    hash.update("\0");
    hash.update(fs.readFileSync(path.join(root, file)));
    hash.update("\0");
  }
  return `sha256:${hash.digest("hex")}`;
}

function assertVerifierDigest(expectedPath = DIGEST_PATH, root = VERIFIER_ROOT) {
  const expected = fs.readFileSync(expectedPath, "utf8").trim();
  const observed = verifierDigest(root);
  if (observed !== expected) {
    const error = new Error("baked Tempo verifier does not match the task digest");
    error.phase = "verifier-integrity";
    error.expected = expected;
    error.observed = observed;
    throw error;
  }
}

if (require.main === module) console.log(verifierDigest());

module.exports = { assertVerifierDigest, verifierDigest };
