import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";

import {
  CanaryRegistryMirrorError,
  canonicalJson,
  verifyCanaryRegistryMirror,
} from "../server-modules/canary-registry-mirror.mjs";

function sha256(value) {
  return createHash("sha256").update(value).digest("hex");
}

function domainHash(domain, payload) {
  return sha256(canonicalJson({ domain, payload }));
}

function snapshot(generation = 0) {
  const body = {
    contract_id: "room16.canary_registry_snapshot",
    schema_version: 2,
    authority_owner: "research",
    registry_generation: generation,
    previous_registry_sha256: null,
    ledger_head_sha256: "1".repeat(64),
    entries: [],
  };
  return {
    ...body,
    snapshot_sha256: domainHash("room16.canary_registry_snapshot@2", body),
  };
}

function authorityReceipt(source) {
  assert.equal(source.snapshot_sha256, "0ec92ccd6fafcb33bda80c04634994eda06020f01769bd254018e494ccc5dc8a");
  return {
    contract_id: "room16.canary_research_snapshot_authority_receipt",
    schema_version: 1,
    authority_owner: "research",
    receipt_id: "receipt.test.pinned.fixture",
    research_key_id: "research.canary.registry.primary",
    research_role: "canary_registry_authority",
    snapshot_sha256: source.snapshot_sha256,
    registry_head_sha256: "2".repeat(64),
    issued_at_utc: "2026-08-20T00:00:00Z",
    signature_algorithm: "ed25519",
    signature: "cbaf9129726dfe01b6fc5184940fecb097a73514d0e7db7013600cadcf5d5bce1c5d977d84e2c8e9a5e510dec9f26ef6de2ab53f5b1924ebec336c689f867906",
    receipt_sha256: "d09b0e093e4bde08e6d4b424be8ff8ec10f311821b8c2fee1231b251d2834ece",
  };
}

test("exact mirror bound to pinned Research receipt passes read-only", () => {
  const source = snapshot();
  const verdict = verifyCanaryRegistryMirror(structuredClone(source), authorityReceipt(source));
  assert.equal(verdict.receipt_state, "valid");
  assert.equal(verdict.product_may_select_expected_hash, false);
  assert.equal(verdict.product_may_promote_research_truth, false);
  assert.equal(Object.isFrozen(verdict), true);
});

test("caller-created Research-labeled snapshot cannot choose the trusted hash", () => {
  const trusted = snapshot();
  const forged = snapshot(999);
  assert.throws(
    () => verifyCanaryRegistryMirror(forged, authorityReceipt(trusted)),
    (error) => error instanceof CanaryRegistryMirrorError
      && error.diagnosticCode === "BA11_CONSUMER_MIRROR_INVALID",
  );
  assert.equal(verifyCanaryRegistryMirror.length, 2);
});

test("forged or tampered Research receipt is blocked", () => {
  const source = snapshot();
  const receipt = authorityReceipt(source);
  assert.throws(
    () => verifyCanaryRegistryMirror(source, { ...receipt, signature: "0".repeat(128) }),
    (error) => error instanceof CanaryRegistryMirrorError
      && error.diagnosticCode === "BA11_RESEARCH_AUTHORITY_UNTRUSTED",
  );
});

test("mirror drift and Product authority relabel fail closed", () => {
  const source = snapshot();
  const drift = { ...source, registry_generation: 1 };
  assert.throws(
    () => verifyCanaryRegistryMirror(drift, authorityReceipt(source)),
    (error) => error instanceof CanaryRegistryMirrorError
      && error.diagnosticCode === "BA11_HASH_MISMATCH",
  );
  const relabeledBody = { ...source, authority_owner: "product" };
  delete relabeledBody.snapshot_sha256;
  const relabeled = {
    ...relabeledBody,
    snapshot_sha256: domainHash("room16.canary_registry_snapshot@2", relabeledBody),
  };
  assert.throws(
    () => verifyCanaryRegistryMirror(relabeled, authorityReceipt(source)),
    (error) => error instanceof CanaryRegistryMirrorError
      && error.diagnosticCode === "BA11_SCHEMA_INVALID",
  );
});
