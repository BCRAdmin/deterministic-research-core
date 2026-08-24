#!/usr/bin/env python3
"""Standalone verifier for deterministic RFC-0009 acceptance-freeze evidence."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


DOMAIN = b"room16.rfc0009.native_trust_freeze.evidence.manifest@1\0"
FREEZE_SHA256 = "e9c9e6e5e5573961207babd66d7c981504d118ed4d14e87f7d6a8ca4180904b9"
REQUIRED = {
    "00_RFC0009_FREEZE_VERDICT.md",
    "01_EXTERNAL_INDEPENDENT_ACCEPTANCE.json",
    "02_RFC0009_FREEZE_RECORD.json",
    "03_RFC0009_FREEZE_VERIFIER_RECEIPT.json",
    "04_RFC0009_FREEZE_MATRIX_RECEIPT.json",
    "05_FULL_REGRESSION_RECEIPTS.json",
    "06_BA10_BA11_RFC0008_FREEZE_RECEIPTS.json",
    "07_R2_SOURCE_VERIFIER_RECEIPT.json",
    "08_GIT_TREE_BINDINGS.json",
    "09_FOREIGN_WORKTREE_BOUNDARY.json",
    "10_DETERMINISTIC_BUILD_REPORT.json",
    "11_PHASE_A_STATUS.json",
    "independent_verifier/verify_rfc0009_native_trust_freeze_evidence.py",
    "MANIFEST.json",
}


def manifest_hash(value: dict[str, Any]) -> str:
    body = {**value, "manifest_sha256": ""}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(DOMAIN + canonical).hexdigest()


def verify_package(package: Path) -> dict[str, Any]:
    package_bytes = package.read_bytes()
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if archive.testzip() is not None or len(names) != len(set(names)) or set(names) != REQUIRED:
            raise ValueError("RFC9_FREEZE_EVIDENCE_MEMBER_SET_INVALID")
        if any((item.external_attr >> 16) & 0o777 != 0o644 for item in archive.infolist()):
            raise ValueError("RFC9_FREEZE_EVIDENCE_MEMBER_MODE_INVALID")
        manifest = json.loads(archive.read("MANIFEST.json"))
        if manifest_hash(manifest) != manifest.get("manifest_sha256"):
            raise ValueError("RFC9_FREEZE_EVIDENCE_MANIFEST_HASH_INVALID")
        payloads = manifest.get("payloads", [])
        if [row["path"] for row in payloads] != sorted(REQUIRED - {"MANIFEST.json"}):
            raise ValueError("RFC9_FREEZE_EVIDENCE_MANIFEST_CLOSURE_INVALID")
        for row in payloads:
            payload = archive.read(row["path"])
            if len(payload) != row["bytes"] or hashlib.sha256(payload).hexdigest() != row["sha256"]:
                raise ValueError("RFC9_FREEZE_EVIDENCE_PAYLOAD_HASH_INVALID")
        freeze = json.loads(archive.read("02_RFC0009_FREEZE_RECORD.json"))
        verifier = json.loads(archive.read("03_RFC0009_FREEZE_VERIFIER_RECEIPT.json"))
        matrix = json.loads(archive.read("04_RFC0009_FREEZE_MATRIX_RECEIPT.json"))
        regressions = json.loads(archive.read("05_FULL_REGRESSION_RECEIPTS.json"))
        dependencies = json.loads(archive.read("06_BA10_BA11_RFC0008_FREEZE_RECEIPTS.json"))
        r2 = json.loads(archive.read("07_R2_SOURCE_VERIFIER_RECEIPT.json"))
        boundary = json.loads(archive.read("09_FOREIGN_WORKTREE_BOUNDARY.json"))
        deterministic = json.loads(archive.read("10_DETERMINISTIC_BUILD_REPORT.json"))
        status = json.loads(archive.read("11_PHASE_A_STATUS.json"))
        if freeze.get("freeze_sha256") != FREEZE_SHA256 or verifier.get("status") != "PASS":
            raise ValueError("RFC9_FREEZE_EVIDENCE_FREEZE_INVALID")
        if matrix.get("passed") != 20 or matrix.get("failed") != 0:
            raise ValueError("RFC9_FREEZE_EVIDENCE_MATRIX_INVALID")
        if any(row.get("status") != "PASS" for row in regressions.get("receipts", [])):
            raise ValueError("RFC9_FREEZE_EVIDENCE_REGRESSION_INVALID")
        if any(row.get("status") != "PASS" for row in dependencies.get("receipts", [])):
            raise ValueError("RFC9_FREEZE_EVIDENCE_DEPENDENCY_INVALID")
        if r2.get("status") != "PASS" or r2.get("manifest_sha256") != freeze["source_r2"]["manifest_sha256"]:
            raise ValueError("RFC9_FREEZE_EVIDENCE_R2_INVALID")
        if boundary.get("status") != "PASS" or boundary.get("unchanged") is not True:
            raise ValueError("RFC9_FREEZE_EVIDENCE_BOUNDARY_INVALID")
        if deterministic.get("byte_identical_rebuild") is not True:
            raise ValueError("RFC9_FREEZE_EVIDENCE_REBUILD_INVALID")
        expected = {
            "rfc0009_independent_rereview": "ACCEPTED",
            "rfc0009_implementation_ready": True,
            "rfc0009_frozen": True,
            "ba12_resume_authorized": True,
            "release_authorized": False,
            "publication_authorized": False,
            "deploy_authorized": False,
        }
        if any(status.get(key) != value for key, value in expected.items()):
            raise ValueError("RFC9_FREEZE_EVIDENCE_STATUS_INVALID")
    return {
        "contract_id": "room16.rfc0009.native_trust_freeze.evidence_verifier@1",
        "status": "PASS",
        "package": package.name,
        "package_bytes": len(package_bytes),
        "package_sha256": hashlib.sha256(package_bytes).hexdigest(),
        "zip_entries": len(names),
        "manifest_sha256": manifest["manifest_sha256"],
        "freeze_sha256": FREEZE_SHA256,
        "freeze_matrix_passed": 20,
        "rfc0009_frozen": True,
        "ba12_resume_authorized": True,
        "release_authorized": False,
    }


def main() -> int:
    print(json.dumps(verify_package(Path(sys.argv[1]).resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
