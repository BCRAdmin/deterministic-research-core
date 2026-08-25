#!/usr/bin/env python3
"""Standalone verifier for RFC-0010 acceptance/freeze evidence."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

DOMAIN = b"room16.rfc0010.freeze.evidence_manifest@1\0"
FREEZE_SHA256 = "05f46f421f0da768424c125e39cabb86eb88b6c3fde7201d270a71725705ab6c"
R2_SHA256 = "4aee8c0d0fe2329f21cc3878ac5144352128abfc184e0ae2048e676b53c02b47"
REQUIRED = {
    "00_RFC0010_FREEZE_VERDICT.md",
    "01_EXTERNAL_INDEPENDENT_ACCEPTANCE.json",
    "02_RFC0010_FREEZE_RECORD.json",
    "03_RFC0010_FREEZE_VERIFIER_RECEIPT.json",
    "04_RFC0010_FREEZE_MATRIX_EXECUTED.json",
    "05_FULL_REGRESSION_RECEIPTS.json",
    "06_DEPENDENCY_FREEZE_RECEIPTS.json",
    "07_R2_SOURCE_VERIFIER_RECEIPT.json",
    "08_GIT_TREE_BINDINGS.json",
    "09_FOREIGN_BOUNDARY_BEFORE.json",
    "10_FOREIGN_BOUNDARY_PRE_PUSH.json",
    "11_PROJECT_BOUNDARY_NON_INTERFERENCE_V2_RECEIPT.json",
    "12_PHASE_A_RUNTIME_DIFF.json",
    "13_DETERMINISTIC_BUILD_REPORT.json",
    "14_PHASE_A_STATUS.json",
    "15_BOUNDARY_GATE_V2_HANDOFF_BINDING.json",
    "MANIFEST.json",
    "independent_verifier/VERIFIER_RECEIPT.json",
    "independent_verifier/verify_rfc0010_freeze_evidence.py",
}


def manifest_hash(value: dict[str, Any]) -> str:
    body = {**value, "manifest_sha256": ""}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(DOMAIN + encoded).hexdigest()


def _json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    value = json.loads(archive.read(name))
    if not isinstance(value, dict):
        raise ValueError(f"RFC10_FREEZE_JSON_OBJECT_REQUIRED:{name}")
    return value


def verify_package(package: Path) -> dict[str, Any]:
    package_bytes = package.read_bytes()
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if set(names) != REQUIRED or len(names) != len(set(names)):
            raise ValueError("RFC10_FREEZE_MEMBER_SET_INVALID")
        if archive.testzip() is not None:
            raise ValueError("RFC10_FREEZE_ZIP_INVALID")
        if any((item.external_attr >> 16) & 0o777 != 0o644 for item in archive.infolist()):
            raise ValueError("RFC10_FREEZE_MEMBER_MODE_INVALID")
        manifest = _json(archive, "MANIFEST.json")
        if manifest_hash(manifest) != manifest.get("manifest_sha256"):
            raise ValueError("RFC10_FREEZE_MANIFEST_HASH_INVALID")
        records = manifest.get("payloads")
        if not isinstance(records, list) or [item.get("path") for item in records] != sorted(REQUIRED - {"MANIFEST.json"}):
            raise ValueError("RFC10_FREEZE_MANIFEST_CLOSURE_INVALID")
        for item in records:
            payload = archive.read(item["path"])
            if len(payload) != item.get("bytes") or hashlib.sha256(payload).hexdigest() != item.get("sha256"):
                raise ValueError("RFC10_FREEZE_PAYLOAD_HASH_INVALID")

        acceptance = _json(archive, "01_EXTERNAL_INDEPENDENT_ACCEPTANCE.json")
        freeze = _json(archive, "02_RFC0010_FREEZE_RECORD.json")
        verifier = _json(archive, "03_RFC0010_FREEZE_VERIFIER_RECEIPT.json")
        matrix = _json(archive, "04_RFC0010_FREEZE_MATRIX_EXECUTED.json")
        regressions = _json(archive, "05_FULL_REGRESSION_RECEIPTS.json")
        dependencies = _json(archive, "06_DEPENDENCY_FREEZE_RECEIPTS.json")
        r2 = _json(archive, "07_R2_SOURCE_VERIFIER_RECEIPT.json")
        bindings = _json(archive, "08_GIT_TREE_BINDINGS.json")
        boundary = _json(archive, "11_PROJECT_BOUNDARY_NON_INTERFERENCE_V2_RECEIPT.json")
        runtime_diff = _json(archive, "12_PHASE_A_RUNTIME_DIFF.json")
        deterministic = _json(archive, "13_DETERMINISTIC_BUILD_REPORT.json")
        status = _json(archive, "14_PHASE_A_STATUS.json")
        embedded = _json(archive, "independent_verifier/VERIFIER_RECEIPT.json")
        boundary_binding = _json(archive, "15_BOUNDARY_GATE_V2_HANDOFF_BINDING.json")

        if acceptance.get("verdict") != "ACCEPTED" or acceptance.get("remaining_blocking_findings") != 0:
            raise ValueError("RFC10_FREEZE_ACCEPTANCE_INVALID")
        if freeze.get("freeze_sha256") != FREEZE_SHA256 or freeze.get("status") != "accepted_frozen":
            raise ValueError("RFC10_FREEZE_RECORD_INVALID")
        if verifier.get("status") != "PASS" or verifier.get("freeze_sha256") != FREEZE_SHA256:
            raise ValueError("RFC10_FREEZE_VERIFIER_RECEIPT_INVALID")
        rows = matrix.get("rows")
        expected_ids = [f"RFC10-F-T-{number:03d}" for number in range(1, 25)]
        if (
            matrix.get("status") != "PASS"
            or matrix.get("row_count") != 24
            or not isinstance(rows, list)
            or [row.get("test_id") for row in rows] != expected_ids
            or any(row.get("actual") != row.get("expected") for row in rows)
            or any("test_rfc0010_freeze_matrix" not in str(row.get("node_id", "")) for row in rows)
        ):
            raise ValueError("RFC10_FREEZE_MATRIX_INVALID")
        for group in (regressions, dependencies):
            if group.get("status") != "PASS" or any(item.get("status") != "PASS" for item in group.get("receipts", [])):
                raise ValueError("RFC10_FREEZE_REGRESSION_INVALID")
        if r2.get("status") != "PASS" or r2.get("package_sha256") != R2_SHA256 or r2.get("matrix_rows_passed") != 37:
            raise ValueError("RFC10_FREEZE_R2_SOURCE_INVALID")
        if (
            bindings.get("research", {}).get("origin") != "https://github.com/BCRAdmin/deterministic-research-core.git"
            or bindings.get("product", {}).get("origin") != "https://github.com/BCRAdmin/company-dossier-lab.git"
        ):
            raise ValueError("RFC10_FREEZE_BINDINGS_INVALID")
        before = _json(archive, "09_FOREIGN_BOUNDARY_BEFORE.json")
        after = _json(archive, "10_FOREIGN_BOUNDARY_PRE_PUSH.json")
        if (
            boundary.get("contract_id") != "room16.project_boundary_non_interference@2"
            or boundary.get("verdict") != "PASS"
            or boundary.get("common_dir_overlap") is not False
            or boundary.get("path_root_overlap") is not False
            or boundary.get("foreign_targeting_mutating_commands") != []
            or boundary.get("room16_foreign_write_paths") != []
            or boundary.get("room16_foreign_mutation") is not False
            or boundary.get("foreign_repo_used_as_authority_input") is not False
            or boundary.get("output_resolves_into_foreign_root") is not False
            or boundary.get("foreign_before_snapshot_sha256") != before.get("snapshot_sha256")
            or boundary.get("foreign_after_snapshot_sha256") != after.get("snapshot_sha256")
        ):
            raise ValueError("RFC10_FREEZE_FOREIGN_BOUNDARY_INVALID")
        if (
            boundary_binding.get("status") != "PASS"
            or boundary_binding.get("handoff_sha256")
            != "254c00f220d9f3a4fcf5e26923d502a90d6274c4e4dc16a4f28a067f347322aa"
            or boundary_binding.get("previous_stop_evidence_sha256")
            != "a1ebed358f61ce7b1652dfa0f729d886d87661dedf2af7c8625c1480973483d3"
            or boundary_binding.get("supersedes_global_foreign_quiescence") is not True
        ):
            raise ValueError("RFC10_FREEZE_BOUNDARY_V2_BINDING_INVALID")
        if runtime_diff.get("runtime_semantic_changed") is not False or runtime_diff.get("changed_runtime_files") != []:
            raise ValueError("RFC10_FREEZE_RUNTIME_DIFF_INVALID")
        if deterministic.get("byte_identical_rebuild") is not True or embedded.get("status") != "PASS":
            raise ValueError("RFC10_FREEZE_DETERMINISM_INVALID")
        expected_status = {
            "ba12_resume_authorized": True,
            "deploy_authorized": False,
            "publication_authorized": False,
            "release_authorized": False,
            "rfc0010_frozen": True,
            "rfc0010_implementation_ready": True,
            "rfc0010_independent_rereview": "ACCEPTED",
        }
        if any(status.get(key) != value for key, value in expected_status.items()):
            raise ValueError("RFC10_FREEZE_FINAL_STATUS_INVALID")
        verdict = archive.read("00_RFC0010_FREEZE_VERDICT.md")
        if any(marker not in verdict for marker in (b"rfc0010_frozen=true", b"ba12_resume_authorized=true", b"release_authorized=false", b"publication_authorized=false", b"deploy_authorized=false")):
            raise ValueError("RFC10_FREEZE_VERDICT_MARKERS_INVALID")
    return {
        "ba12_resume_authorized": True,
        "contract_id": "room16.rfc0010.freeze_evidence_verifier@1",
        "deploy_authorized": False,
        "freeze_sha256": FREEZE_SHA256,
        "manifest_sha256": manifest["manifest_sha256"],
        "matrix_rows_passed": 24,
        "package": package.name,
        "package_bytes": len(package_bytes),
        "package_sha256": hashlib.sha256(package_bytes).hexdigest(),
        "publication_authorized": False,
        "release_authorized": False,
        "rfc0010_frozen": True,
        "status": "PASS",
        "zip_entries": len(names),
    }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_rfc0010_freeze_evidence.py PACKAGE")
    print(json.dumps(verify_package(Path(sys.argv[1]).resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
