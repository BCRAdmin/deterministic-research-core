#!/usr/bin/env python3
"""Independently verify the complete BA11 R4 evidence package."""

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

SOURCE_R4_SHA256 = "6301148f84af486a631280469d4cf496f17dc8bbdbecffba47de03350a838d11"
SOURCE_R3_SHA256 = "c2a1850d1e6928def976fa0459398f930429b2007adcd5e7e6efc339e84ad80e"
FINDING_IDS = (
    "BA11-R3-RR-P0-001", "BA11-R3-RR-P0-002", "BA11-R3-RR-P0-003",
    "BA11-R3-RR-P0-004", "BA11-R3-RR-P0-005", "BA11-R3-RR-P0-006",
    "BA11-R3-RR-P0-007", "BA11-R3-RR-P1-001", "BA11-R3-RR-P1-002",
    "BA11-R3-RR-P1-003",
)
REQUIRED = {
    "00_R4_CORRECTION_VERDICT.md", "01_INPUT_LOCK.json", "02_R3_REREVIEW_FINDINGS.json",
    "03_REOPENED_R1_RR2_STATUS_MATRIX.json", "04_R4_FINDING_CLOSURE_REGISTER.json",
    "05_AUTHORITY_GRAPH_REPORT.json", "06_TRANSACTION_OBJECT_SET_REPORT.json",
    "07_LEDGER_PERSISTENCE_AND_ROLLBACK_REPORT.json",
    "08_APPEND_VALIDATE_BEFORE_WRITE_REPORT.json", "09_APPROVAL_SUBJECT_BINDING_REPORT.json",
    "10_RECOVERY_FAULT_INJECTION_REPORT.json", "11_COMPARISON_CHAIN_REPORT.json",
    "12_CANARY_ID_VERSION_GENESIS_REPORT.json", "13_ROLE_KEY_SEPARATION_REPORT.json",
    "14_AUTHORITATIVE_ACCEPTANCE_REGISTER.json", "15_TEST_MATRIX_EXECUTED.json",
    "16_FULL_REGRESSION_RECEIPTS.json", "17_BA10_RAW_VERIFIER_RECEIPT.json",
    "18_SOURCE_TREE_BINDINGS.json", "19_CHANGED_FILES_PER_FINDING.json",
    "20_DETERMINISTIC_BUILD_REPORT.json", "21_FOREIGN_WORKTREE_BOUNDARY_REPORT.json",
    "22_REREVIEW_REQUEST.md", "MANIFEST.json", "independent_verifier/VERIFIER_RECEIPT.json",
    "source/ROOM16_BA11_ARCHITECTURE_R1_CORRECTED_REREVIEW_R3_CF229F7F4E3A_2026-08-19.zip",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _json(members: dict[str, bytes], name: str) -> dict[str, Any]:
    return json.loads(members[name])


def _test_names(source: bytes) -> set[str]:
    return set(re.findall(rb"^def (test_[a-zA-Z0-9_]+)\(", source, flags=re.MULTILINE))


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
    if lock.get("source_r4_sha256") != SOURCE_R4_SHA256 or any(
        lock.get(key) != value for key, value in gates.items()
    ):
        raise ValueError("input lock or final gate mismatch")
    source_name = next(name for name in members if name.startswith("source/") and name.endswith(".zip"))
    if sha256_bytes(members[source_name]) != SOURCE_R3_SHA256:
        raise ValueError("nested R3 source hash mismatch")
    findings = _json(members, "02_R3_REREVIEW_FINDINGS.json")["findings"]
    if tuple(row["finding_id"] for row in findings) != FINDING_IDS:
        raise ValueError("R4 finding set mismatch")
    closure = _json(members, "04_R4_FINDING_CLOSURE_REGISTER.json")
    if tuple(row["finding_id"] for row in closure["findings"]) != FINDING_IDS:
        raise ValueError("closure finding set mismatch")
    source_test_path = "implementation/research/research_agent/tests/test_canary_governance_r4.py"
    if source_test_path not in members:
        raise ValueError("authoritative R4 source tests missing")
    source_names = {name.decode() for name in _test_names(members[source_test_path])}
    acceptance = _json(members, "14_AUTHORITATIVE_ACCEPTANCE_REGISTER.json")
    executed = _json(members, "15_TEST_MATRIX_EXECUTED.json")
    verify_acceptance_register(acceptance, executed, source_test_names=source_names)
    receipts = _json(members, "16_FULL_REGRESSION_RECEIPTS.json")["receipts"]
    if any(row.get("exit_code") != 0 for row in receipts):
        raise ValueError("one or more command receipts failed")
    if _json(members, "17_BA10_RAW_VERIFIER_RECEIPT.json").get("parsed_stdout", {}).get("status") != "PASS":
        raise ValueError("BA10 verifier did not pass")
    changed = _json(members, "19_CHANGED_FILES_PER_FINDING.json")
    for row in changed["files"]:
        package_path = f"implementation/{row['repo']}/{row['path']}"
        if package_path not in members or sha256_bytes(members[package_path]) != row["sha256"]:
            raise ValueError(f"changed-file binding mismatch: {package_path}")
    if _json(members, "21_FOREIGN_WORKTREE_BOUNDARY_REPORT.json").get("foreign_scope_touched_by_room16_run"):
        raise ValueError("foreign worktree boundary violated")
    receipt = {
        "contract_id": "room16.ba11_r4.independent_verifier_receipt@1",
        "schema_version": 1,
        "verifier_owner": "independent_verifier",
        "status": "PASS",
        "checks": [
            "required_members", "input_lock", "nested_r3_source", "ten_findings",
            "authoritative_54_row_acceptance", "source_test_resolution", "command_receipts",
            "ba10_raw_verifier", "changed_file_hashes", "foreign_boundary",
        ],
        "finding_count": len(findings),
        "acceptance_row_count": len(acceptance["rows"]),
        "executed_row_count": len(executed["rows"]),
        "ready_for_independent_rereview": True,
        "ba11_implementation_ready": False,
        "ba12_authorized": False,
        "release_authorized": False,
        "publication_authorized": False,
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
        {name: value for name, value in members.items() if name not in {"MANIFEST.json", "independent_verifier/VERIFIER_RECEIPT.json"}}
    )
    actual_receipt = _json(members, "independent_verifier/VERIFIER_RECEIPT.json")
    if actual_receipt != expected_receipt:
        raise ValueError("independent verifier receipt mismatch")
    assert_independent_closure(_json(members, "04_R4_FINDING_CLOSURE_REGISTER.json"), actual_receipt)
    return {
        "status": "PASS", "archive": archive_path.name, "archive_bytes": len(archive_bytes),
        "archive_sha256": archive_sha, "manifest_sha256": manifest.manifest_sha256,
        "member_count": len(members), "finding_count": len(FINDING_IDS),
        "acceptance_row_count": 54, "deterministic_rebuild": True,
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
