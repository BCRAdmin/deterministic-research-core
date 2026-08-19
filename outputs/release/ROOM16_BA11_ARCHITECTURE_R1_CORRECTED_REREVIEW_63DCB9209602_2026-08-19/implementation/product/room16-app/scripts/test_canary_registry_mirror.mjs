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

function snapshot() {
  const body = {
    contract_id: "room16.canary_registry_snapshot",
    schema_version: 1,
    authority_owner: "research",
    registry_generation: 0,
    previous_registry_sha256: null,
    ledger_head_sha256: "1".repeat(64),
    entries: [],
  };
  return {
    ...body,
    snapshot_sha256: sha256(canonicalJson({
      domain: "room16.canary_registry_snapshot@1",
      payload: body,
    })),
  };
}

test("product consumes an exact Research snapshot read-only", () => {
  const source = snapshot();
  const verdict = verifyCanaryRegistryMirror(source, structuredClone(source));
  assert.equal(verdict.receipt_state, "valid");
  assert.equal(verdict.product_may_promote_research_truth, false);
  assert.equal(Object.isFrozen(verdict), true);
});

test("mirror drift blocks Product but cannot stale Research", () => {
  const source = snapshot();
  const mirror = structuredClone(source);
  mirror.registry_generation = 1;
  assert.throws(
    () => verifyCanaryRegistryMirror(source, mirror),
    (error) => error instanceof CanaryRegistryMirrorError && error.diagnosticCode === "BA11_HASH_MISMATCH",
  );
  assert.equal(source.registry_generation, 0);
});

test("Product authority relabel fails closed", () => {
  const source = snapshot();
  const mirror = { ...source, authority_owner: "product" };
  assert.throws(
    () => verifyCanaryRegistryMirror(source, mirror),
    (error) => error instanceof CanaryRegistryMirrorError && error.diagnosticCode === "BA11_CONSUMER_MIRROR_INVALID",
  );
});
