#!/usr/bin/env python3
"""Prove the frozen RFC-0008 trust policy cannot accept truthful BA12 native identity."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import canonical_bytes, sha256_json
from research_agent.productization_v2.artifact_bundle import (
    ArtifactBundleV2Error,
    verify_compiler_artifact_bundle_v2,
)
from research_agent.productization_v2.contracts import CompilerArtifactBundleManifestV2

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
CONFIG = ROOT / "research_agent/productization_v2/config"
CANARY = CONFIG / "migration_canaries/WM"
FREEZE = ROOT / "docs/compiler_foundation/freezes/" / (
    "RFC0008_COMPILER_ARTIFACT_BUNDLE_V2_TRUST_FREEZE_v1.json"
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def native_probe() -> tuple[dict[str, Any], str]:
    manifest = load(CANARY / "BUNDLE_MANIFEST.json")
    manifest["compiler_identity"]["semantic_artifact_origin"] = "source_native"
    manifest["compile_identity"].update(
        {
            "compile_request_sha256": "1" * 64,
            "source_acquisition_sha256": "2" * 64,
            "retrieval_receipt_set_sha256": "3" * 64,
            "source_snapshot_sha256": "4" * 64,
            "migration_v1_bundle_sha256": None,
        }
    )
    manifest["compatibility"].update(
        {
            "mode": "bundle_native",
            "compiler_mode": "source_native",
            "source_native_fact_generation": True,
            "native_source_production": True,
        }
    )
    manifest["bundle_sha256"] = sha256_json(
        {key: value for key, value in manifest.items() if key != "bundle_sha256"}
    )
    model = CompilerArtifactBundleManifestV2.model_validate(manifest)
    model.verify_bundle_hash()
    with tempfile.TemporaryDirectory(prefix="room16-ba12-native-trust-probe-") as temporary:
        target = Path(temporary) / "bundle"
        shutil.copytree(CANARY, target)
        (target / "BUNDLE_MANIFEST.json").write_bytes(canonical_bytes(manifest))
        try:
            verify_compiler_artifact_bundle_v2(target)
        except ArtifactBundleV2Error as exc:
            return manifest, exc.code
    return manifest, "UNEXPECTED_PASS"


def verify(product_repo: Path) -> dict[str, Any]:
    policy_envelope = load(CONFIG / "consumer_policy_envelope_v2.json")
    profile = load(CONFIG / "manifest_schema_profile_v2.json")
    product_profile = load(
        product_repo / "room16-app/config/room16_compiler_artifact_bundle_schema_profile_v2.json"
    )
    manifest, diagnostic = native_probe()
    frozen_origin = policy_envelope["payload"]["compiler_identity"][
        "semantic_artifact_origin"
    ]
    profile_origin = profile["compiler_identity_lock"]["semantic_artifact_origin"]
    product_origin = product_profile["compiler_identity_lock"]["semantic_artifact_origin"]
    checks = {
        "rfc0008_freeze_present": FREEZE.is_file(),
        "bundle_v2_contract_accepts_source_native_identity": (
            manifest["compiler_identity"]["semantic_artifact_origin"] == "source_native"
            and manifest["compatibility"]["mode"] == "bundle_native"
            and manifest["compatibility"]["compiler_mode"] == "source_native"
            and manifest["compatibility"]["source_native_fact_generation"] is True
            and manifest["compatibility"]["native_source_production"] is True
        ),
        "consumer_policy_pins_migration_origin": frozen_origin == "frozen_v1_migration",
        "research_schema_pins_migration_origin": profile_origin == "frozen_v1_migration",
        "product_schema_pins_migration_origin": product_origin == "frozen_v1_migration",
        "truthful_native_bundle_rejected_by_frozen_verifier": (
            diagnostic == "RFC8_TRUST_POLICY_MISMATCH"
        ),
        "research_product_schema_profiles_byte_identical": (
            sha(CONFIG / "manifest_schema_profile_v2.json")
            == sha(
                product_repo
                / "room16-app/config/room16_compiler_artifact_bundle_schema_profile_v2.json"
            )
        ),
    }
    if not all(checks.values()):
        raise SystemExit("STOP native trust conflict probe did not reproduce exact boundary")
    return {
        "contract_id": "room16.ba12.native_trust_conflict_stop_evidence@1",
        "schema_version": 1,
        "status": "STOPPED_RFC_TRIGGER_REQUIRED",
        "diagnostic_code": diagnostic,
        "stop_conditions": [2, 6, 7, 8],
        "root_cause": (
            "The frozen RFC-0008 Consumer Policy and Research/Product schema profiles "
            "pin CompilerIdentityV2.semantic_artifact_origin=frozen_v1_migration. "
            "CompilerArtifactBundle@2 permits source_native, but both frozen verifiers "
            "require exact equality with the migration-only compiler identity lock."
        ),
        "required_rfc_decision": (
            "A new independently accepted trust-policy generation or successor trust root "
            "must define and sign a source_native CompilerIdentityV2 lock without weakening "
            "the existing migration trust boundary."
        ),
        "checks": checks,
        "bindings": {
            "rfc0008_freeze_sha256": load(FREEZE)["freeze_sha256"],
            "consumer_policy_sha256": policy_envelope["payload"]["policy_sha256"],
            "consumer_policy_envelope_file_sha256": sha(
                CONFIG / "consumer_policy_envelope_v2.json"
            ),
            "research_schema_profile_file_sha256": sha(
                CONFIG / "manifest_schema_profile_v2.json"
            ),
            "research_v2_contract_file_sha256": sha(
                ROOT / "research_agent/productization_v2/contracts.py"
            ),
            "research_v2_verifier_file_sha256": sha(
                ROOT / "research_agent/productization_v2/artifact_bundle.py"
            ),
            "product_v2_schema_profile_file_sha256": sha(
                product_repo
                / "room16-app/config/room16_compiler_artifact_bundle_schema_profile_v2.json"
            ),
            "product_v2_verifier_file_sha256": sha(
                product_repo / "room16-app/server-modules/compiler-artifact-bundle-v2.mjs"
            ),
        },
        "native_probe": {
            "contract_model_validation": "PASS",
            "compiler_identity_semantic_artifact_origin": "source_native",
            "mode": "bundle_native",
            "compiler_mode": "source_native",
            "source_native_fact_generation": True,
            "native_source_production": True,
            "frozen_verifier_result": diagnostic,
        },
        "forbidden_actions_preserved": {
            "frozen_v2_policy_changed": False,
            "frozen_v2_verifier_changed": False,
            "ba10_or_ba11_changed": False,
            "product_changed": False,
            "release": False,
            "publication": False,
            "deploy": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-repo", type=Path, default=PRODUCT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify(args.product_repo.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
