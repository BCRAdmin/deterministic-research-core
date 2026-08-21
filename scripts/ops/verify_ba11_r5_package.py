#!/usr/bin/env python3
"""Independently verify the complete BA11 R5 evidence package."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import zipfile
from pathlib import Path
from typing import Any

from research_agent.canary_governance.acceptance import (
    assert_independent_closure,
    verify_acceptance_register,
)
from research_agent.canary_governance.archive import build_deterministic_zip
from research_agent.canary_governance.contracts import EvidenceManifest, EvidencePackageIdentity

SOURCE_R5_SHA256 = "edded26224567b087b852d9e9f631271b9b2e27dd917ad438ca63a3f5a951cd7"
SOURCE_R4_SHA256 = "cd45138728ec20c2c9a6cad2fbce5e25a56c99b599da58606098560753d80f46"
SOURCE_R5_NAME = "ROOM16_BA11_R4_INDEPENDENT_REREVIEW_R5_CHANGES_REQUIRED_VEGA_CORRECTION_EDDED2622456_2026-08-21.zip"
SOURCE_R4_NAME = "ROOM16_BA11_ARCHITECTURE_R1_CORRECTED_REREVIEW_R4_AEB23345B864_2026-08-20.zip"
FINDING_IDS = (
    "BA11-R4-RR-P0-001",
    "BA11-R4-RR-P0-002",
    "BA11-R4-RR-P0-003",
    "BA11-R4-RR-P1-001",
)
REQUIRED = {
    "00_R5_CORRECTION_VERDICT.md",
    "01_INPUT_LOCK.json",
    "02_R5_FINDINGS.json",
    "03_R5_FINDING_CLOSURE_REGISTER.json",
    "04_STAGING_PUBLICATION_ISOLATION_REPORT.json",
    "05_MULTI_GENERATION_LIFECYCLE_REPORT.json",
    "06_REGISTRY_HEAD_ROLLBACK_REPORT.json",
    "07_ACCEPTANCE_NODEID_REPORT.json",
    "08_TEST_MATRIX_EXECUTED.json",
    "09_R4_REGRESSION_REPORT.json",
    "10_FULL_REGRESSION_RECEIPTS.json",
    "11_BA10_RAW_VERIFIER_RECEIPT.json",
    "12_SOURCE_TREE_BINDINGS.json",
    "13_CHANGED_FILES_PER_FINDING.json",
    "14_DETERMINISTIC_BUILD_REPORT.json",
    "15_FOREIGN_WORKTREE_BOUNDARY_REPORT.json",
    "16_REREVIEW_REQUEST.md",
    "MANIFEST.json",
    "independent_verifier/VERIFIER_RECEIPT.json",
    f"source/{SOURCE_R5_NAME}",
    f"source/{SOURCE_R4_NAME}",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _json(members: dict[str, bytes], name: str) -> dict[str, Any]:
    return json.loads(members[name])


def _source_test_names(source: bytes) -> set[str]:
    return {
        name.decode()
        for name in re.findall(rb"^def (test_[a-zA-Z0-9_]+)\(", source, flags=re.MULTILINE)
    }


def derive_verifier_receipt(members: dict[str, bytes]) -> dict[str, Any]:
    missing = REQUIRED - {"MANIFEST.json", "independent_verifier/VERIFIER_RECEIPT.json"} - set(members)
    if missing:
        raise ValueError(f"missing required members: {sorted(missing)}")
    lock = _json(members, "01_INPUT_LOCK.json")
    gates = {
        "ready_for_independent_rereview": True,
        "ba11_implementation_ready": False,
        "ba12_authorized": False,
        "release_authorized": False,
        "publication_authorized": False,
    }
    if (
        lock.get("source_r5_sha256") != SOURCE_R5_SHA256
        or lock.get("source_r4_sha256") != SOURCE_R4_SHA256
        or any(lock.get(key) != value for key, value in gates.items())
    ):
        raise ValueError("input lock or final gate mismatch")
    if sha256_bytes(members[f"source/{SOURCE_R5_NAME}"]) != SOURCE_R5_SHA256:
        raise ValueError("source R5 contract hash mismatch")
    if sha256_bytes(members[f"source/{SOURCE_R4_NAME}"]) != SOURCE_R4_SHA256:
        raise ValueError("source R4 result hash mismatch")
    findings = _json(members, "02_R5_FINDINGS.json")["findings"]
    closure = _json(members, "03_R5_FINDING_CLOSURE_REGISTER.json")["findings"]
    if tuple(row["finding_id"] for row in findings) != FINDING_IDS:
        raise ValueError("R5 finding set mismatch")
    if tuple(row["finding_id"] for row in closure) != FINDING_IDS:
        raise ValueError("R5 closure set mismatch")
    test_path = "implementation/research/research_agent/tests/test_canary_governance_r5.py"
    if test_path not in members:
        raise ValueError("authoritative R5 source tests missing")
    executed = _json(members, "08_TEST_MATRIX_EXECUTED.json")
    verify_acceptance_register(
        executed["required_matrix"],
        executed,
        source_test_names=_source_test_names(members[test_path]),
    )
    if len(executed.get("rows", [])) != 18:
        raise ValueError("R5 acceptance row count mismatch")
    receipts = _json(members, "10_FULL_REGRESSION_RECEIPTS.json")["receipts"]
    required_receipts = {
        "r5_collect",
        "targeted_r5",
        "targeted_r4",
        "research_full",
        "research_ruff",
        "product_pytest",
        "product_hardening",
        "product_full",
        "ba10_freeze",
    }
    if required_receipts - {row.get("receipt_id") for row in receipts}:
        raise ValueError("full regression receipt set incomplete")
    if any(row.get("exit_code") != 0 for row in receipts):
        raise ValueError("one or more command receipts failed")
    if _json(members, "11_BA10_RAW_VERIFIER_RECEIPT.json").get("parsed_stdout", {}).get("status") != "PASS":
        raise ValueError("BA10 verifier did not pass")
    for name in (
        "04_STAGING_PUBLICATION_ISOLATION_REPORT.json",
        "05_MULTI_GENERATION_LIFECYCLE_REPORT.json",
        "06_REGISTRY_HEAD_ROLLBACK_REPORT.json",
        "07_ACCEPTANCE_NODEID_REPORT.json",
        "09_R4_REGRESSION_REPORT.json",
        "14_DETERMINISTIC_BUILD_REPORT.json",
    ):
        if _json(members, name).get("status") != "PASS":
            raise ValueError(f"report did not pass: {name}")
    changed = _json(members, "13_CHANGED_FILES_PER_FINDING.json")
    for row in changed["files"]:
        packaged = f"implementation/{row['repo']}/{row['path']}"
        if packaged not in members or sha256_bytes(members[packaged]) != row["sha256"]:
            raise ValueError(f"changed file binding mismatch: {packaged}")
    boundary = _json(members, "15_FOREIGN_WORKTREE_BOUNDARY_REPORT.json")
    if boundary.get("foreign_scope_touched_by_room16_run") is not False:
        raise ValueError("foreign worktree boundary violated")
    receipt = {
        "contract_id": "room16.ba11_r5.independent_verifier_receipt@1",
        "schema_version": 1,
        "verifier_owner": "independent_verifier",
        "status": "PASS",
        "checks": [
            "required_members",
            "input_lock",
            "source_r5_contract",
            "source_r4_result",
            "four_findings",
            "exact_18_nodeid_acceptance",
            "full_regressions",
            "ba10_raw_verifier",
            "changed_file_hashes",
            "foreign_boundary",
        ],
        "finding_count": 4,
        "acceptance_row_count": 18,
        **gates,
    }
    receipt["verifier_receipt_sha256"] = sha256_bytes(json_bytes(receipt))
    return receipt


def verify_package(archive_path: Path, sidecar_path: Path, identity_path: Path) -> dict[str, Any]:
    archive_bytes = archive_path.read_bytes()
    archive_sha = sha256_bytes(archive_bytes)
    if sidecar_path.read_bytes() != f"{archive_sha}  {archive_path.name}\n".encode():
        raise ValueError("detached SHA-256 mismatch")
    identity = EvidencePackageIdentity.model_validate_json(identity_path.read_text(encoding="utf-8"))
    if (
        identity.package_filename != archive_path.name
        or identity.package_bytes != len(archive_bytes)
        or identity.package_sha256 != archive_sha
        or identity.detached_sha256_filename != sidecar_path.name
    ):
        raise ValueError("package identity mismatch")
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
        members = {name: archive.read(name) for name in names}
    manifest = EvidenceManifest.model_validate_json(members["MANIFEST.json"])
    if manifest.manifest_sha256 != identity.manifest_sha256:
        raise ValueError("manifest identity mismatch")
    listed = {row.path: row for row in manifest.files}
    payload = set(members) - {"MANIFEST.json"}
    if set(listed) != payload:
        raise ValueError("manifest payload scope mismatch")
    for name in payload:
        if listed[name].bytes != len(members[name]) or listed[name].sha256 != sha256_bytes(members[name]):
            raise ValueError(f"manifest member mismatch: {name}")
    rebuilt, rebuilt_manifest = build_deterministic_zip(
        {name: members[name] for name in payload}, source_date_epoch=manifest.source_date_epoch
    )
    if rebuilt != archive_bytes or rebuilt_manifest != manifest.model_dump(mode="json"):
        raise ValueError("deterministic ZIP rebuild mismatch")
    expected_receipt = derive_verifier_receipt(
        {
            name: value
            for name, value in members.items()
            if name not in {"MANIFEST.json", "independent_verifier/VERIFIER_RECEIPT.json"}
        }
    )
    actual_receipt = _json(members, "independent_verifier/VERIFIER_RECEIPT.json")
    if actual_receipt != expected_receipt:
        raise ValueError("independent verifier receipt mismatch")
    assert_independent_closure(_json(members, "03_R5_FINDING_CLOSURE_REGISTER.json"), actual_receipt)
    return {
        "status": "PASS",
        "archive": archive_path.name,
        "archive_bytes": len(archive_bytes),
        "archive_sha256": archive_sha,
        "manifest_sha256": manifest.manifest_sha256,
        "member_count": len(members),
        "finding_count": 4,
        "acceptance_row_count": 18,
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
