#!/usr/bin/env python3
"""Standalone verifier for RFC-0009 R2 freeze-compatibility evidence."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

DOMAIN = b"room16.rfc0009.r2_freeze_compatibility.evidence.manifest@1\0"
ROOT_SHA256 = "56a94fcd6eede746dc2778f05774bc46f80cd50be02cf3302027aab729f8a356"
GEN1_ENVELOPE_SHA256 = "7f16189fdfd6b676fd3cb58acf9c6c51a9a1b66671dbb7c1f76156dffc5cd8c9"
RFC0008_FREEZE_SHA256 = "27636f891457a98a790702f8fbba19763e0a8b363978c205c9eca54361a84fb0"
SOURCE_R1_SHA256 = "42d3513da453176cd8824ed2f1c4930b3c3d3f95b497e6cbddd39107f4af2052"
SOURCE_R2_SHA256 = "5b4155d5850334fe8201ec75cd1e156ff1f3cffc358964c26361b130fbd1e8ce"
REQUIRED = {
    "00_R2_IMPLEMENTATION_VERDICT.md",
    "01_R2_FINDINGS.json",
    "02_BASELINE_LOCK.json",
    "03_RFC_0009_R2_DELTA.md",
    "04_NATIVE_EMITTER_CONTRACT_PROFILE.json",
    "05_GEN2_POLICY_ENVELOPE_FINAL.json",
    "06_NATIVE_SCHEMA_PROFILE_FINAL.json",
    "07_EMITTER_DYNAMIC_IMPLEMENTATION_REPORT.json",
    "08_BA12_ELIGIBILITY_COMPATIBILITY_REPORT.json",
    "09_PRODUCT_NATIVE_VERIFIER_REPORT.json",
    "10_RESEARCH_NATIVE_VERIFIER_REPORT.json",
    "11_ROUTER_REGRESSION_REPORT.json",
    "12_R2_ACCEPTANCE_MATRIX_EXECUTED.json",
    "13_R1_REGRESSION_MATRIX.json",
    "14_RFC0008_BA10_BA11_FREEZE_REGRESSION.json",
    "15_FULL_REGRESSION_RECEIPTS.json",
    "16_SOURCE_TREE_BINDINGS.json",
    "17_CHANGED_FILES_PER_FINDING.json",
    "18_PRIVATE_KEY_ABSENCE_REPORT.json",
    "19_FOREIGN_WORKTREE_BOUNDARY_REPORT.json",
    "20_DETERMINISTIC_BUILD_REPORT.json",
    "21_INDEPENDENT_REREVIEW_REQUEST.md",
    "MANIFEST.json",
    "independent_verifier/VERIFIER_RECEIPT.json",
    "independent_verifier/verify_rfc0009_r2_freeze_compatibility_evidence.py",
    "source_patches/research.patch",
    "source_patches/product.patch",
}


def manifest_hash(value: dict[str, Any]) -> str:
    body = {**value, "manifest_sha256": ""}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(DOMAIN + canonical).hexdigest()


def verify_package(package: Path) -> dict[str, Any]:
    package_bytes = package.read_bytes()
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or not REQUIRED <= set(names):
            raise ValueError("RFC9_R2_EVIDENCE_MEMBER_SET_INVALID")
        if any((item.external_attr >> 16) & 0o777 != 0o644 for item in archive.infolist()):
            raise ValueError("RFC9_R2_EVIDENCE_MEMBER_MODE_INVALID")
        manifest = json.loads(archive.read("MANIFEST.json"))
        if manifest_hash(manifest) != manifest["manifest_sha256"]:
            raise ValueError("RFC9_R2_EVIDENCE_MANIFEST_HASH_INVALID")
        records = manifest["payloads"]
        if [item["path"] for item in records] != sorted(set(names) - {"MANIFEST.json"}):
            raise ValueError("RFC9_R2_EVIDENCE_MANIFEST_CLOSURE_INVALID")
        for item in records:
            payload = archive.read(item["path"])
            if len(payload) != item["bytes"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
                raise ValueError("RFC9_R2_EVIDENCE_PAYLOAD_HASH_INVALID")

        findings = json.loads(archive.read("01_R2_FINDINGS.json"))
        baseline = json.loads(archive.read("02_BASELINE_LOCK.json"))
        emitter = json.loads(archive.read("04_NATIVE_EMITTER_CONTRACT_PROFILE.json"))
        envelope = json.loads(archive.read("05_GEN2_POLICY_ENVELOPE_FINAL.json"))
        schema = json.loads(archive.read("06_NATIVE_SCHEMA_PROFILE_FINAL.json"))
        dynamic = json.loads(archive.read("07_EMITTER_DYNAMIC_IMPLEMENTATION_REPORT.json"))
        eligibility = json.loads(archive.read("08_BA12_ELIGIBILITY_COMPATIBILITY_REPORT.json"))
        product = json.loads(archive.read("09_PRODUCT_NATIVE_VERIFIER_REPORT.json"))
        research = json.loads(archive.read("10_RESEARCH_NATIVE_VERIFIER_REPORT.json"))
        router = json.loads(archive.read("11_ROUTER_REGRESSION_REPORT.json"))
        matrix = json.loads(archive.read("12_R2_ACCEPTANCE_MATRIX_EXECUTED.json"))
        freezes = json.loads(archive.read("14_RFC0008_BA10_BA11_FREEZE_REGRESSION.json"))
        regressions = json.loads(archive.read("15_FULL_REGRESSION_RECEIPTS.json"))
        bindings = json.loads(archive.read("16_SOURCE_TREE_BINDINGS.json"))
        private = json.loads(archive.read("18_PRIVATE_KEY_ABSENCE_REPORT.json"))
        foreign = json.loads(archive.read("19_FOREIGN_WORKTREE_BOUNDARY_REPORT.json"))
        deterministic = json.loads(archive.read("20_DETERMINISTIC_BUILD_REPORT.json"))
        embedded = json.loads(archive.read("independent_verifier/VERIFIER_RECEIPT.json"))

        lock = emitter.get("emitter_contract_lock", {})
        if (
            findings.get("counts", {}).get("total") != 3
            or baseline.get("source_r1", {}).get("sha256") != SOURCE_R1_SHA256
            or baseline.get("rfc0008_freeze_sha256") != RFC0008_FREEZE_SHA256
            or emitter.get("contract_version") != 2
            or "emitter_identity" in emitter
            or "implementation_sha256" in lock
            or lock.get("implementation_binding") != "research_signed_bundle_receipt"
            or lock.get("implementation_sha256_rule") != "required_64_hex_dynamic"
            or schema.get("native_emitter_lock") != lock
            or envelope.get("previous_envelope_sha256") != GEN1_ENVELOPE_SHA256
            or dynamic.get("status") != "PASS"
            or dynamic.get("distinct_implementation_hashes") is not True
            or dynamic.get("mismatch_blocked") is not True
            or eligibility.get("status") != "PASS"
            or eligibility.get("release_publication_deploy_blocked") is not True
            or any(report.get("status") != "PASS" for report in (product, research, router))
        ):
            raise ValueError("RFC9_R2_EVIDENCE_COMPATIBILITY_SEMANTICS_INVALID")
        if matrix.get("row_count") != 38 or len(matrix.get("rows", [])) != 38 or any(row.get("status") != "PASS" or row.get("actual") != row.get("expected") for row in matrix["rows"]):
            raise ValueError("RFC9_R2_EVIDENCE_MATRIX_INVALID")
        if (
            freezes.get("status") != "PASS"
            or freezes.get("rfc0008", {}).get("freeze_sha256") != RFC0008_FREEZE_SHA256
            or any(item.get("status") != "PASS" for item in regressions.get("receipts", []))
            or bindings.get("source_r2", {}).get("sha256") != SOURCE_R2_SHA256
            or bindings.get("trust_root_sha256") != ROOT_SHA256
            or private.get("status") != "PASS"
            or private.get("private_key_found") is not False
            or foreign.get("status") != "PASS"
            or foreign.get("unchanged") is not True
            or deterministic.get("byte_identical_builds") is not True
            or embedded.get("status") != "PASS"
        ):
            raise ValueError("RFC9_R2_EVIDENCE_REGRESSION_OR_BOUNDARY_INVALID")
        markers = (b"-----BEGIN " + b"PRIVATE KEY-----", b"OPENSSH " + b"PRIVATE KEY")
        for name in names:
            if any(marker in archive.read(name) for marker in markers):
                raise ValueError("RFC9_R2_EVIDENCE_PRIVATE_KEY_MARKER")
    return {
        "contract_id": "room16.rfc0009.r2_freeze_compatibility.evidence_verifier@1",
        "status": "PASS",
        "package": package.name,
        "package_bytes": len(package_bytes),
        "package_sha256": hashlib.sha256(package_bytes).hexdigest(),
        "zip_entries": len(names),
        "manifest_sha256": manifest["manifest_sha256"],
        "matrix_rows_passed": 38,
        "trust_root_sha256": ROOT_SHA256,
        "ready_for_independent_rereview": True,
        "rfc0009_implementation_ready": False,
        "rfc0009_frozen": False,
        "ba12_resume_authorized": False,
    }


def main() -> int:
    print(json.dumps(verify_package(Path(sys.argv[1]).resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
