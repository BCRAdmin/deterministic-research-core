import { createHash } from "node:crypto";

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

function verifySnapshotHash(snapshot) {
  const body = { ...snapshot };
  const declared = body.snapshot_sha256;
  delete body.snapshot_sha256;
  if (domainHash("room16.canary_registry_snapshot@1", body) !== declared) {
    throw new CanaryRegistryMirrorError("BA11_HASH_MISMATCH", "snapshot_sha256");
  }
}

export function verifyCanaryRegistryMirror(researchSnapshot, productMirror) {
  if (
    researchSnapshot?.contract_id !== "room16.canary_registry_snapshot" ||
    researchSnapshot?.schema_version !== 1 ||
    researchSnapshot?.authority_owner !== "research"
  ) {
    throw new CanaryRegistryMirrorError("BA11_SCHEMA_INVALID", "research_snapshot");
  }
  if (productMirror?.authority_owner !== "research") {
    throw new CanaryRegistryMirrorError("BA11_CONSUMER_MIRROR_INVALID", "authority_relabel");
  }
  verifySnapshotHash(researchSnapshot);
  verifySnapshotHash(productMirror);
  if (canonicalJson(researchSnapshot) !== canonicalJson(productMirror)) {
    throw new CanaryRegistryMirrorError("BA11_CONSUMER_MIRROR_INVALID", "hash_drift");
  }
  return Object.freeze({
    contract_id: "room16.canary_consumer_mirror_verdict",
    schema_version: 1,
    authority_owner: "product_consumer",
    mirror_mode: "hash_verified_read_only",
    research_snapshot_sha256: researchSnapshot.snapshot_sha256,
    mirrored_snapshot_sha256: productMirror.snapshot_sha256,
    receipt_state: "valid",
    product_may_promote_research_truth: false,
  });
}
