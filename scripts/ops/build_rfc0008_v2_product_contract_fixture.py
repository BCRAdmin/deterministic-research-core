#!/usr/bin/env python3
"""Build a tiny signed Product fixture under the pinned Research trust chain."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from nacl.signing import SigningKey

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_json
from research_agent.productization.contracts import (
    REQUIRED_ARTIFACT_KINDS,
    REQUIRED_BUNDLE_SECTION_IDS,
    ArtifactRecord,
    BundleSectionRecord,
)
from research_agent.productization_v2.artifact_bundle import (
    load_consumer_policy_v2,
    load_public_key_policy_v2,
)
from research_agent.productization_v2.contracts import (
    CompileIdentityV2,
    CompilerArtifactBundleManifestV2,
    CompilerIdentityV2,
    CompatibilityStateV2,
    EligibilityStateV2,
    EmitterIdentityV2,
)
from research_agent.productization_v2.trust_receipt import sign_bundle_receipt_v2

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
OUTPUT = PRODUCT / "room16-app/fixtures/compiler-artifact-bundle-v2-pinned"
PRIVATE_KEY = ROOT / ".runtime/rfc0008/signing_key_ed25519.bin"


def main() -> int:
    if not PRIVATE_KEY.is_file() or PRIVATE_KEY.stat().st_size != 32:
        raise SystemExit("STOP Research-only RFC-0008 signing key is missing")
    policy = load_consumer_policy_v2()
    key_policy = load_public_key_policy_v2()
    key_id = next(item.key_id for item in key_policy.keys if item.state == "active")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    (OUTPUT / "artifacts").mkdir(parents=True)
    artifacts = []
    for kind in REQUIRED_ARTIFACT_KINDS:
        relative_path = f"artifacts/{kind}.json"
        payload = canonical_bytes(
            {
                "contract_id": f"room16.rfc0008.fixture.{kind}",
                "contract_version": 1,
                "fixture": True,
            }
        )
        (OUTPUT / relative_path).write_bytes(payload)
        artifacts.append(
            ArtifactRecord(
                artifact_id=f"fixture.{kind}",
                artifact_kind=kind,
                contract_id=f"room16.rfc0008.fixture.{kind}",
                contract_version=1,
                layer="L11",
                producer_pass_id="rfc0008.r2.product_contract_fixture",
                relative_path=relative_path,
                media_type="application/json",
                sha256=sha256_json(json.loads(payload)),
                byte_length=len(payload),
                required=True,
                authoritative=kind != "authority_v3_bridge",
                compatibility_only=kind == "authority_v3_bridge",
            )
        )
    artifacts = sorted(artifacts, key=lambda item: item.artifact_id)
    sections = []
    artifact_ids = {item.artifact_kind: item.artifact_id for item in artifacts}
    for section_id in REQUIRED_BUNDLE_SECTION_IDS:
        linked = (artifact_ids[section_id],) if section_id in artifact_ids else ()
        sections.append(
            BundleSectionRecord(
                section_id=section_id,
                schema_version="2.0.0",
                sha256=sha256_json({"fixture_section": section_id, "artifact_ids": linked}),
                compatibility_rule="exact_version",
                required=True,
                artifact_ids=linked,
            )
        )
    sections = sorted(sections, key=lambda item: item.section_id)
    compiler_identity = CompilerIdentityV2(semantic_artifact_origin="frozen_v1_migration")
    compile_identity = CompileIdentityV2(
        ticker="WM",
        as_of_date="2026-08-11",
        final_compile_state_sha256="a" * 64,
        verification_report_sha256="b" * 64,
        replay_sha256="c" * 64,
        migration_v1_bundle_sha256="d" * 64,
    )
    emitter = EmitterIdentityV2(
        implementation_sha256="e" * 64,
        schema_sha256="f" * 64,
        consumer_policy_sha256=policy.policy_sha256,
    )
    body = {
        "contract_id": "room16.compiler_artifact_bundle",
        "contract_version": 2,
        "schema_version": "2.0.0",
        "canonicalization_profile": "room16.foundation.canonical_json@1",
        "hash_algorithm": "sha256",
        "compiler_identity": compiler_identity.model_dump(mode="json"),
        "emitter_identity": emitter.model_dump(mode="json"),
        "compile_identity": compile_identity.model_dump(mode="json"),
        "compatibility": CompatibilityStateV2(
            mode="bundle_dual_read",
            compiler_mode="migration_dual_read",
            source_native_fact_generation=False,
            native_source_production=False,
            authority_v3_bridge_direction="bundle_to_authority_v3_only",
        ).model_dump(mode="json"),
        "eligibility": EligibilityStateV2(
            compile_allowed=True,
            renderer_eligible=True,
        ).model_dump(mode="json"),
        "ba10_v1_freeze_sha256": policy.ba10_v1_freeze_sha256,
        "ba11_freeze_sha256": policy.ba11_freeze_sha256,
        "artifact_index_sha256": sha256_json([item.model_dump(mode="json") for item in artifacts]),
        "artifacts": [item.model_dump(mode="json") for item in artifacts],
        "section_index_sha256": sha256_json([item.model_dump(mode="json") for item in sections]),
        "sections": [item.model_dump(mode="json") for item in sections],
        "required_sections": list(REQUIRED_ARTIFACT_KINDS),
        "optional_sections": [],
        "extensions": {"fixture": {"production_authority": False}},
    }
    body["bundle_sha256"] = sha256_json(body)
    manifest = CompilerArtifactBundleManifestV2.model_validate(body)
    manifest.verify_bundle_hash()
    (OUTPUT / "BUNDLE_MANIFEST.json").write_bytes(canonical_bytes(manifest.model_dump(mode="json")))
    receipt = sign_bundle_receipt_v2(
        {
            "contract_id": "room16.compiler_artifact_bundle_receipt",
            "contract_version": 2,
            "receipt_id": "rfc0008.product.pinned_fixture",
            "bundle_sha256": manifest.bundle_sha256,
            "compile_identity_sha256": sha256_json(manifest.compile_identity),
            "compiler_identity_sha256": sha256_json(manifest.compiler_identity),
            "emitter_identity_sha256": sha256_json(manifest.emitter_identity),
            "policy_sha256": policy.policy_sha256,
            "ba10_v1_freeze_sha256": manifest.ba10_v1_freeze_sha256,
            "ba11_freeze_sha256": manifest.ba11_freeze_sha256,
            "research_key_id": key_id,
            "issued_at_utc": "2026-08-21T01:00:00Z",
            "not_after_utc": None,
            "monotonic_counter": 100,
            "nonce": "rfc0008-product-pinned-fixture-20260821",
            "signature_algorithm": "ed25519",
        },
        signing_key=SigningKey(PRIVATE_KEY.read_bytes()),
    )
    (OUTPUT / "RECEIPT.json").write_text(
        json.dumps(receipt.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "PASS",
                "fixture": str(OUTPUT),
                "bundle_sha256": manifest.bundle_sha256,
                "receipt_sha256": receipt.receipt_sha256,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
