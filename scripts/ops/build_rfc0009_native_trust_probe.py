#!/usr/bin/env python3
"""Build a synthetic, signed native Bundle@2 trust probe for RFC-0009."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from nacl.signing import SigningKey

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.productization_v2.native_trust import (
    CONFIG_ROOT,
    verify_native_bundle_v2,
)
from research_agent.productization_v2.trust_receipt import sign_bundle_receipt_v2

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
SOURCE = PRODUCT / "room16-app/fixtures/compiler-artifact-bundle-v2-pinned"
RESEARCH_FIXTURE = ROOT / "research_agent/tests/fixtures/rfc0009-native-probe"
PRODUCT_FIXTURE = PRODUCT / "room16-app/fixtures/rfc0009-native-probe"
LEAF_KEY = ROOT / ".runtime/rfc0008/signing_key_ed25519.bin"


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build(target: Path) -> dict:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(SOURCE, target)
    manifest_path = target / "BUNDLE_MANIFEST.json"
    receipt_path = target / "RECEIPT.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    policy = json.loads(
        (CONFIG_ROOT / "consumer_policy_v2_generation_2_native.json").read_text(
            encoding="utf-8"
        )
    )
    emitter_profile = json.loads(
        (CONFIG_ROOT / "native_emitter_profile_v2.json").read_text(encoding="utf-8")
    )
    manifest["compiler_identity"]["semantic_artifact_origin"] = "source_native"
    manifest["emitter_identity"] = {
        **emitter_profile["emitter_identity"],
        "consumer_policy_sha256": policy["policy_sha256"],
    }
    manifest["compile_identity"].update(
        {
            "compile_request_sha256": sha256_json("rfc0009-native-compile-request"),
            "source_acquisition_sha256": sha256_json("rfc0009-native-source-acquisition"),
            "retrieval_receipt_set_sha256": sha256_json("rfc0009-native-retrieval-receipts"),
            "source_snapshot_sha256": sha256_json("rfc0009-native-source-snapshot"),
            "migration_v1_bundle_sha256": None,
        }
    )
    manifest["compatibility"] = {
        "authority_v3_bridge_direction": "bundle_to_authority_v3_only",
        "authority_v3_semantic_input_allowed": False,
        "compiler_mode": "source_native",
        "legacy_semantic_input_allowed": False,
        "mode": "bundle_native",
        "native_source_production": True,
        "source_native_fact_generation": True,
    }
    manifest["eligibility"].update(
        {
            "ba12_cutover_candidate": False,
            "deploy_allowed": False,
            "publication_allowed": False,
            "release_ready": False,
            "renderer_cutover": False,
            "renderer_eligible": False,
        }
    )
    manifest["extensions"] = {
        "rfc0009_native_trust_probe": {
            "canonical": False,
            "company_canary": False,
            "production_authority": False,
            "synthetic": True,
        }
    }
    section_hashes = {
        "artifact_hashes": sha256_json(manifest["artifacts"]),
        "compatibility_state": sha256_json(manifest["compatibility"]),
        "compile_identity": sha256_json(manifest["compile_identity"]),
        "compiler_version": sha256_json(manifest["compiler_identity"]),
        "ir_references": sha256_json(
            [
                {"artifact_id": item["artifact_id"], "sha256": item["sha256"]}
                for item in manifest["artifacts"]
                if item["authoritative"]
            ]
        ),
    }
    for section in manifest["sections"]:
        if section["section_id"] in section_hashes:
            section["sha256"] = section_hashes[section["section_id"]]
    manifest["artifact_index_sha256"] = sha256_json(manifest["artifacts"])
    manifest["section_index_sha256"] = sha256_json(manifest["sections"])
    body = {key: value for key, value in manifest.items() if key != "bundle_sha256"}
    manifest["bundle_sha256"] = sha256_json(body)
    write_json(manifest_path, manifest)

    key_policy = json.loads(
        (CONFIG_ROOT / "public_key_policy_v2.json").read_text(encoding="utf-8")
    )
    signing_key = SigningKey(LEAF_KEY.read_bytes())
    if signing_key.verify_key.encode().hex() != key_policy["keys"][0]["public_key_hex"]:
        raise SystemExit("STOP RFC-0008 leaf signing key mismatch")
    receipt = sign_bundle_receipt_v2(
        {
            "contract_id": "room16.compiler_artifact_bundle_receipt",
            "contract_version": 2,
            "receipt_id": "rfc0008.rfc0009.native_trust_probe",
            "bundle_sha256": manifest["bundle_sha256"],
            "compile_identity_sha256": sha256_json(manifest["compile_identity"]),
            "compiler_identity_sha256": sha256_json(manifest["compiler_identity"]),
            "emitter_identity_sha256": sha256_json(manifest["emitter_identity"]),
            "policy_sha256": policy["policy_sha256"],
            "ba10_v1_freeze_sha256": manifest["ba10_v1_freeze_sha256"],
            "ba11_freeze_sha256": manifest["ba11_freeze_sha256"],
            "research_key_id": key_policy["keys"][0]["key_id"],
            "issued_at_utc": "2026-08-22T00:05:00Z",
            "not_after_utc": None,
            "monotonic_counter": 2,
            "nonce": "rfc0009.native.probe.0001",
            "signature_algorithm": "ed25519",
        },
        signing_key=signing_key,
    )
    write_json(receipt_path, receipt.model_dump(mode="json"))
    return verify_native_bundle_v2(target, receipt=receipt)


def main() -> int:
    result = build(RESEARCH_FIXTURE)
    if PRODUCT_FIXTURE.exists():
        shutil.rmtree(PRODUCT_FIXTURE)
    shutil.copytree(RESEARCH_FIXTURE, PRODUCT_FIXTURE)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
