import fs from "node:fs";
import path from "node:path";
import { createHash, createPublicKey, verify as verifySignature } from "node:crypto";
import { fileURLToPath } from "node:url";

const TRUST_POLICY_FILE = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../config/room16_canary_registry_trust_policy_v1.json",
);
const TRUST_POLICY_SHA256 = "24315fd9e7784322219ea0927df78738f37a3cf1fb7b482af0c6c04faab2c7f4";
const SNAPSHOT_FIELDS = new Set([
  "contract_id", "schema_version", "authority_owner", "registry_generation",
  "previous_registry_sha256", "ledger_head_sha256", "entries", "snapshot_sha256",
]);
const RECEIPT_FIELDS = new Set([
  "contract_id", "schema_version", "authority_owner", "receipt_id", "research_key_id",
  "research_role", "snapshot_sha256", "registry_head_sha256", "issued_at_utc",
  "signature_algorithm", "signature", "receipt_sha256",
]);

export class CanaryRegistryMirrorError extends Error {
  constructor(diagnosticCode, detail = "") {
    super(`${diagnosticCode}:${detail}`);
    this.name = "CanaryRegistryMirrorError";
    this.diagnosticCode = diagnosticCode;
  }
}

function normalize(value) {
  if (value === null || typeof value === "boolean" || typeof value === "string") return value;
  if (typeof value === "number") {
    if (!Number.isFinite(value) || (Number.isInteger(value) && !Number.isSafeInteger(value))) {
      throw new CanaryRegistryMirrorError("BA11_SCHEMA_INVALID", "number");
    }
    return Object.is(value, -0) ? 0 : value;
  }
  if (Array.isArray(value)) return value.map(normalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, normalize(value[key])]));
  }
  throw new CanaryRegistryMirrorError("BA11_SCHEMA_INVALID", typeof value);
}

export function canonicalJson(value) {
  return JSON.stringify(normalize(value));
}

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function domainHash(domain, payload) {
  return sha256(canonicalJson({ domain, payload }));
}

function exactFields(value, expected, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new CanaryRegistryMirrorError("BA11_SCHEMA_INVALID", label);
  }
  const actual = Object.keys(value);
  if (actual.length !== expected.size || actual.some((field) => !expected.has(field))) {
    throw new CanaryRegistryMirrorError("BA11_SCHEMA_INVALID", `${label}_fields`);
  }
}

function trustedResearchPolicy() {
  let policy;
  try {
    policy = JSON.parse(fs.readFileSync(TRUST_POLICY_FILE, "utf8"));
  } catch (error) {
    throw new CanaryRegistryMirrorError("BA11_RESEARCH_AUTHORITY_UNTRUSTED", error.message);
  }
  const body = { ...policy };
  delete body.policy_sha256;
  if (
    policy.contract_id !== "room16.product.canary_registry_trust_policy" ||
    policy.schema_version !== 1 ||
    policy.owner !== "research" ||
    policy.product_may_select_expected_hash !== false ||
    policy.product_may_promote_research_truth !== false ||
    policy.policy_sha256 !== TRUST_POLICY_SHA256 ||
    sha256(canonicalJson(body)) !== TRUST_POLICY_SHA256
  ) {
    throw new CanaryRegistryMirrorError("BA11_RESEARCH_AUTHORITY_UNTRUSTED", "policy");
  }
  return policy;
}

function verifySnapshotHash(snapshot, policy) {
  exactFields(snapshot, SNAPSHOT_FIELDS, "snapshot");
  if (
    snapshot.contract_id !== policy.snapshot_contract_id ||
    snapshot.schema_version !== policy.snapshot_schema_version ||
    snapshot.authority_owner !== "research"
  ) {
    throw new CanaryRegistryMirrorError("BA11_SCHEMA_INVALID", "snapshot");
  }
  const body = { ...snapshot };
  const declared = body.snapshot_sha256;
  delete body.snapshot_sha256;
  if (domainHash("room16.canary_registry_snapshot@2", body) !== declared) {
    throw new CanaryRegistryMirrorError("BA11_HASH_MISMATCH", "snapshot_sha256");
  }
}

function verifyResearchReceipt(receipt, policy) {
  exactFields(receipt, RECEIPT_FIELDS, "research_receipt");
  if (
    receipt.contract_id !== policy.receipt_contract_id ||
    receipt.schema_version !== policy.receipt_schema_version ||
    receipt.authority_owner !== "research" ||
    receipt.research_role !== "canary_registry_authority" ||
    receipt.research_key_id !== policy.trusted_research_key_id ||
    receipt.signature_algorithm !== "ed25519"
  ) {
    throw new CanaryRegistryMirrorError("BA11_RESEARCH_AUTHORITY_UNTRUSTED", "receipt_policy");
  }
  const hashed = { ...receipt };
  const receiptHash = hashed.receipt_sha256;
  delete hashed.receipt_sha256;
  if (domainHash("room16.canary.research_snapshot_authority_receipt@1", hashed) !== receiptHash) {
    throw new CanaryRegistryMirrorError("BA11_RESEARCH_AUTHORITY_UNTRUSTED", "receipt_hash");
  }
  const signed = { ...receipt };
  delete signed.signature;
  delete signed.receipt_sha256;
  const publicKey = createPublicKey({
    key: Buffer.concat([
      Buffer.from("302a300506032b6570032100", "hex"),
      Buffer.from(policy.ed25519_public_key_hex, "hex"),
    ]),
    format: "der",
    type: "spki",
  });
  if (!verifySignature(null, Buffer.from(canonicalJson(signed)), publicKey, Buffer.from(receipt.signature, "hex"))) {
    throw new CanaryRegistryMirrorError("BA11_RESEARCH_AUTHORITY_UNTRUSTED", "signature");
  }
}

export function verifyCanaryRegistryMirror(productMirror, researchAuthorityReceipt) {
  const policy = trustedResearchPolicy();
  verifySnapshotHash(productMirror, policy);
  verifyResearchReceipt(researchAuthorityReceipt, policy);
  if (productMirror.snapshot_sha256 !== researchAuthorityReceipt.snapshot_sha256) {
    throw new CanaryRegistryMirrorError("BA11_CONSUMER_MIRROR_INVALID", "trusted_hash_drift");
  }
  return Object.freeze({
    contract_id: "room16.canary_consumer_mirror_verdict",
    schema_version: 2,
    authority_owner: "product_consumer",
    mirror_mode: policy.mirror_mode,
    research_authority_receipt_sha256: researchAuthorityReceipt.receipt_sha256,
    research_snapshot_sha256: researchAuthorityReceipt.snapshot_sha256,
    mirrored_snapshot_sha256: productMirror.snapshot_sha256,
    receipt_state: "valid",
    product_may_select_expected_hash: false,
    product_may_promote_research_truth: false,
  });
}
