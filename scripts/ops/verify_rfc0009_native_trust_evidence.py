#!/usr/bin/env python3
"""Standalone verifier for RFC-0009 Native Trust Epoch-2 evidence."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

DOMAIN = b"room16.rfc0009.native_trust_epoch2.evidence.manifest@1\0"
REQUIRED = {
    "00_IMPLEMENTATION_VERDICT.md",
    "01_INDEPENDENT_RFC_DECISION.md",
    "02_BASELINE_LOCK.json",
    "03_RFC_0009.md",
    "04_GEN1_GEN2_POLICY_CHAIN_REPORT.json",
    "05_CONSUMER_POLICY_GEN2_ENVELOPE.json",
    "06_NATIVE_SCHEMA_PROFILE.json",
    "07_NATIVE_EMITTER_PROFILE.json",
    "08_NATIVE_TRUST_PROBE_REPORT.json",
    "09_PRODUCT_NATIVE_VERIFIER_REPORT.json",
    "10_ROUTER_SUCCESSOR_REPORT.json",
    "11_ACCEPTANCE_MATRIX_EXECUTED.json",
    "12_RFC0008_FREEZE_REGRESSION.json",
    "13_BA10_BA11_FREEZE_REGRESSION.json",
    "14_FULL_REGRESSION_RECEIPTS.json",
    "15_SOURCE_TREE_BINDINGS.json",
    "16_CHANGED_FILES.json",
    "17_PRIVATE_KEY_ABSENCE_REPORT.json",
    "18_FOREIGN_WORKTREE_BOUNDARY_REPORT.json",
    "19_DETERMINISTIC_BUILD_REPORT.json",
    "20_INDEPENDENT_REREVIEW_REQUEST.md",
    "MANIFEST.json",
    "independent_verifier/VERIFIER_RECEIPT.json",
    "independent_verifier/verify_rfc0009_native_trust_evidence.py",
}
ROOT_SHA256 = "56a94fcd6eede746dc2778f05774bc46f80cd50be02cf3302027aab729f8a356"
GEN1_ENVELOPE_SHA256 = "7f16189fdfd6b676fd3cb58acf9c6c51a9a1b66671dbb7c1f76156dffc5cd8c9"
RFC0008_FREEZE_SHA256 = "27636f891457a98a790702f8fbba19763e0a8b363978c205c9eca54361a84fb0"


def manifest_hash(value: dict[str, Any]) -> str:
    body = {**value, "manifest_sha256": ""}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(DOMAIN + encoded).hexdigest()


def verify_package(package: Path) -> dict[str, Any]:
    package_bytes = package.read_bytes()
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or not REQUIRED <= set(names):
            raise ValueError("RFC9_EVIDENCE_MEMBER_SET_INVALID")
        if any((item.external_attr >> 16) & 0o777 != 0o644 for item in archive.infolist()):
            raise ValueError("RFC9_EVIDENCE_MEMBER_MODE_INVALID")
        manifest = json.loads(archive.read("MANIFEST.json"))
        if manifest_hash(manifest) != manifest["manifest_sha256"]:
            raise ValueError("RFC9_EVIDENCE_MANIFEST_HASH_INVALID")
        records = manifest["payloads"]
        if [item["path"] for item in records] != sorted(set(names) - {"MANIFEST.json"}):
            raise ValueError("RFC9_EVIDENCE_MANIFEST_CLOSURE_INVALID")
        for item in records:
            payload = archive.read(item["path"])
            if len(payload) != item["bytes"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
                raise ValueError("RFC9_EVIDENCE_PAYLOAD_HASH_INVALID")

        chain = json.loads(archive.read("04_GEN1_GEN2_POLICY_CHAIN_REPORT.json"))
        gen2 = json.loads(archive.read("05_CONSUMER_POLICY_GEN2_ENVELOPE.json"))
        schema = json.loads(archive.read("06_NATIVE_SCHEMA_PROFILE.json"))
        emitter = json.loads(archive.read("07_NATIVE_EMITTER_PROFILE.json"))
        probe = json.loads(archive.read("08_NATIVE_TRUST_PROBE_REPORT.json"))
        product = json.loads(archive.read("09_PRODUCT_NATIVE_VERIFIER_REPORT.json"))
        router = json.loads(archive.read("10_ROUTER_SUCCESSOR_REPORT.json"))
        matrix = json.loads(archive.read("11_ACCEPTANCE_MATRIX_EXECUTED.json"))
        rfc8 = json.loads(archive.read("12_RFC0008_FREEZE_REGRESSION.json"))
        ba = json.loads(archive.read("13_BA10_BA11_FREEZE_REGRESSION.json"))
        regressions = json.loads(archive.read("14_FULL_REGRESSION_RECEIPTS.json"))
        changed = json.loads(archive.read("16_CHANGED_FILES.json"))
        private = json.loads(archive.read("17_PRIVATE_KEY_ABSENCE_REPORT.json"))
        foreign = json.loads(archive.read("18_FOREIGN_WORKTREE_BOUNDARY_REPORT.json"))
        deterministic = json.loads(archive.read("19_DETERMINISTIC_BUILD_REPORT.json"))
        embedded = json.loads(archive.read("independent_verifier/VERIFIER_RECEIPT.json"))

        if (
            chain["status"] != "PASS"
            or chain["trust_root_sha256"] != ROOT_SHA256
            or chain["gen1_envelope_sha256"] != GEN1_ENVELOPE_SHA256
            or chain["gen2_generation"] != 2
            or chain["gen2_previous_envelope_sha256"] != GEN1_ENVELOPE_SHA256
            or gen2["payload"]["compiler_identity"]["semantic_artifact_origin"] != "source_native"
            or gen2["payload"]["manifest_schema_profile_sha256"] != schema["profile_sha256"]
            or schema["compiler_identity_lock"]["semantic_artifact_origin"] != "source_native"
            or schema["native_emitter_lock"] != emitter["emitter_identity"]
            or probe["status"] != "PASS"
            or product["status"] != "PASS"
            or router["status"] != "PASS"
        ):
            raise ValueError("RFC9_EVIDENCE_NATIVE_TRUST_SEMANTICS_INVALID")
        if matrix["row_count"] != 47 or len(matrix["rows"]) != 47 or any(row["actual"] != row["expected"] for row in matrix["rows"]):
            raise ValueError("RFC9_EVIDENCE_MATRIX_INVALID")
        if (
            rfc8["status"] != "PASS"
            or rfc8["freeze_sha256"] != RFC0008_FREEZE_SHA256
            or ba["status"] != "PASS"
            or any(item["status"] != "PASS" for item in regressions["receipts"])
            or private["status"] != "PASS"
            or private["private_key_found"] is not False
            or foreign["status"] != "PASS"
            or foreign["unchanged"] is not True
            or deterministic["byte_identical_builds"] is not True
            or embedded["status"] != "PASS"
        ):
            raise ValueError("RFC9_EVIDENCE_REGRESSION_OR_BOUNDARY_INVALID")
        protected = {
            "research_agent/productization_v2/contracts.py",
            "research_agent/productization_v2/artifact_bundle.py",
            "research_agent/productization_v2/trust_root.py",
            "research_agent/productization_v2/schema_profile.py",
            "room16-app/server-modules/compiler-artifact-bundle-v2.mjs",
            "room16-app/server-modules/compiler-artifact-bundle-router.mjs",
        }
        if protected.intersection(changed["research"] + changed["product"]):
            raise ValueError("RFC9_EVIDENCE_GEN1_PROTECTED_CHANGE")
        markers = (
            b"-----BEGIN " + b"PRIVATE KEY-----",
            b"OPENSSH " + b"PRIVATE KEY",
        )
        for name in names:
            payload = archive.read(name)
            if name != "17_PRIVATE_KEY_ABSENCE_REPORT.json" and any(marker in payload for marker in markers):
                raise ValueError("RFC9_EVIDENCE_PRIVATE_KEY_MARKER")
    return {
        "contract_id": "room16.rfc0009.native_trust_epoch2.evidence_verifier@1",
        "status": "PASS",
        "package": package.name,
        "package_bytes": len(package_bytes),
        "package_sha256": hashlib.sha256(package_bytes).hexdigest(),
        "zip_entries": len(names),
        "manifest_sha256": manifest["manifest_sha256"],
        "matrix_rows_passed": 47,
        "trust_root_sha256": ROOT_SHA256,
        "gen2_envelope_sha256": gen2["envelope_sha256"],
        "ready_for_independent_rereview": True,
        "rfc0009_implementation_ready": False,
        "rfc0009_frozen": False,
        "ba12_resume_authorized": False,
    }


def main() -> int:
    result = verify_package(Path(sys.argv[1]).resolve())
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
