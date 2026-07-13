const fs = require("node:fs");
const { isAddress } = require("viem");

const HASH_PATTERN = /^0x[0-9a-fA-F]{64}$/;

function invalid(config, observed) {
  const error = new Error(`invalid result artifact: ${observed}`);
  error.phase = "submission-result";
  error.expected = `${config.resultPath} matches the task output schema`;
  error.observed = observed;
  return error;
}

function expectObject(config, value, keys, label) {
  if (
    value === null ||
    typeof value !== "object" ||
    Array.isArray(value) ||
    Object.keys(value).length !== keys.length ||
    !keys.every((key) => Object.hasOwn(value, key))
  ) {
    throw invalid(config, `${label} must contain ${keys.join(", ")} only`);
  }
  return value;
}

function expectAddress(config, value, label) {
  if (!isAddress(value)) throw invalid(config, `${label} must be an address`);
  return value;
}

function expectHash(config, value, label) {
  if (typeof value !== "string" || !HASH_PATTERN.test(value)) {
    throw invalid(config, `${label} must be a transaction hash`);
  }
  return value;
}

function expectHex32(config, value, label) {
  if (typeof value !== "string" || !HASH_PATTERN.test(value)) {
    throw invalid(config, `${label} must be a 32-byte hex value`);
  }
  return value;
}

function expectUint(config, value, label) {
  if (typeof value !== "string" || !/^\d+$/.test(value)) {
    throw invalid(config, `${label} must be an unsigned integer string`);
  }
  return value;
}

function expectHashes(config, value, label) {
  if (!Array.isArray(value) || !value.length) {
    throw invalid(config, `${label} must be a non-empty array`);
  }
  return value.map((hash, index) => expectHash(config, hash, `${label}[${index}]`));
}

function expectText(config, value, label) {
  if (typeof value !== "string" || !value) throw invalid(config, `${label} must be text`);
  return value;
}

function readResult(config, parse) {
  let result;
  try {
    result = JSON.parse(fs.readFileSync(config.resultPath, "utf8"));
  } catch (error) {
    throw invalid(config, error instanceof Error ? error.message : String(error));
  }
  return parse(result);
}

module.exports = {
  expectAddress,
  expectHash,
  expectHashes,
  expectHex32,
  expectObject,
  expectText,
  expectUint,
  readResult,
};
