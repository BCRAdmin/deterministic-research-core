#!/usr/bin/env python3
"""Verify the delivered BA11 R3 ZIP, detached hash, identity, and derived closure."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import zipfile
from pathlib import Path
from typing import Any

from research_agent.canary_governance.archive import build_deterministic_zip
from research_agent.canary_governance.contracts import EvidenceManifest, EvidencePackageIdentity
from verify_ba11_r3_evidence import ORIGINAL_FINDING_IDS, RR2_FINDING_IDS


REQUIRED = {
    "00_R3_CORRECTION_VERDICT.md",
    "01_INPUT_LOCK.json",
    "02_RR2_FINDINGS.json",
    "03_ORIGINAL_18_CLOSURE_MATRIX.json",
    "04_RR2_FINDING_CLOSURE_REGISTER.json",
    "05_CONTRACT_CATALOG.json",
    "06_IDENTITY_GRAPH.json",
    "07_APPROVAL_AND_REVIEW_TRUST_REPORT.json",
    "08_PRODUCT_AUTHORITY_ANCHOR_REPORT.json",
    "09_LEDGER_ROLLBACK_AND_REPLAY_REPORT.json",
    "10_REGISTRY_TRANSACTION_FAULT_INJECTION_REPORT.json",
    "11_DERIVED_SNAPSHOT_REPORT.json",
    "12_NO_NEW_TRUTH_REPORT.json",
    "13_TEST_MATRIX_EXECUTED.json",
    "14_FULL_REGRESSION_RECEIPTS.json",
    "15_BA10_RAW_VERIFIER_RECEIPT.json",
    "16_SOURCE_TREE_BINDINGS.json",
    "17_CHANGED_FILES_PER_FINDING.json",
    "18_DETERMINISTIC_BUILD_REPORT.json",
    "19_REREVIEW_REQUEST.md",
    "MANIFEST.json",
    "independent_verifier/VERIFIER_RECEIPT.json",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def verify_package(archive_path: Path, sidecar_path: Path, identity_path: Path) -> dict[str, Any]:
    archive_bytes = archive_path.read_bytes()
    archive_sha = sha256_bytes(archive_bytes)
    expected_sidecar = f"{archive_sha}  {archive_path.name}\n".encode()
    if sidecar_path.read_bytes() != expected_sidecar:
        raise ValueError("detached SHA-256 sidecar mismatch")
    identity = EvidencePackageIdentity.model_validate_json(identity_path.read_text(encoding="utf-8"))
    if (
        identity.package_filename != archive_path.name
        or identity.package_bytes != len(archive_bytes)
        or identity.package_sha256 != archive_sha
        or identity.detached_sha256_filename != sidecar_path.name
    ):
        raise ValueError("detached package identity mismatch")

    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip():
            raise ValueError("corrupt ZIP member")
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP member")
        if any(name.startswith("/") or posixpath.normpath(name).startswith("../") for name in names):
            raise ValueError("unsafe ZIP member")
        missing = REQUIRED - set(names)
        if missing:
            raise ValueError(f"missing required members: {sorted(missing)}")
        contents = {name: archive.read(name) for name in names}

    manifest = EvidenceManifest.model_validate_json(contents["MANIFEST.json"])
    if manifest.manifest_sha256 != identity.manifest_sha256:
        raise ValueError("manifest/package identity mismatch")
    listed = {row.path: row for row in manifest.files}
    payload_names = set(names) - {"MANIFEST.json"}
    if set(listed) != payload_names:
        raise ValueError("manifest payload scope mismatch")
    for name in payload_names:
        row = listed[name]
        if row.bytes != len(contents[name]) or row.sha256 != sha256_bytes(contents[name]):
            raise ValueError(f"manifest member mismatch: {name}")
    rebuilt, rebuilt_manifest = build_deterministic_zip(
        {name: contents[name] for name in payload_names},
        source_date_epoch=manifest.source_date_epoch,
    )
    if rebuilt != archive_bytes or rebuilt_manifest != manifest.model_dump(mode="json"):
        raise ValueError("deterministic archive rebuild mismatch")

    verifier_receipt = json.loads(contents["independent_verifier/VERIFIER_RECEIPT.json"])
    receipt_hash = verifier_receipt.pop("verifier_receipt_sha256")
    if receipt_hash != sha256_bytes(canonical_json(verifier_receipt)):
        raise ValueError("independent verifier receipt hash mismatch")
    if verifier_receipt.get("verdict") != "PASS":
        raise ValueError("independent verifier did not pass")
    rr2 = json.loads(contents["04_RR2_FINDING_CLOSURE_REGISTER.json"])["findings"]
    originals = json.loads(contents["03_ORIGINAL_18_CLOSURE_MATRIX.json"])["findings"]
    if tuple(row.get("finding_id") for row in rr2) != RR2_FINDING_IDS:
        raise ValueError("RR2 closure finding set mismatch")
    if any(row.get("verifier_derived_status") != "closed_verified" for row in rr2):
        raise ValueError("RR2 finding is not verifier-closed")
    if tuple(row.get("finding_id") for row in originals) != ORIGINAL_FINDING_IDS:
        raise ValueError("original closure finding set mismatch")
    if any(row.get("status") != "CLOSED_VERIFIED" for row in originals):
        raise ValueError("original finding is not verifier-closed")
    gate = json.loads(contents["01_INPUT_LOCK.json"])
    expected_gate = {
        "ready_for_independent_rereview": True,
        "ba11_implementation_ready": False,
        "ba12_authorized": False,
        "release_authorized": False,
        "publication_authorized": False,
    }
    if any(gate.get(key) != value for key, value in expected_gate.items()):
        raise ValueError("gate state mismatch")
    return {
        "status": "PASS",
        "archive": archive_path.name,
        "archive_bytes": len(archive_bytes),
        "archive_sha256": archive_sha,
        "manifest_sha256": manifest.manifest_sha256,
        "members": len(names),
        "rr2_findings_closed": len(rr2),
        "original_findings_closed": len(originals),
        "deterministic_rebuild": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify_package(args.archive, args.sidecar, args.identity)
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "STOP", "reason": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
