#!/usr/bin/env python3
"""Standalone verifier for the BA12 R3 live-source RFC-trigger package."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


DOMAIN = b"room16.ba12.r3.live_source_rfc_trigger.manifest@1\0"
DIAGNOSTIC = "FROZEN_BA3_LIVE_RECEIPT_TRANSPORT_UNREPRESENTABLE"
SEMANTIC_FREEZE = "62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9"
RFC9_FREEZE = "e9c9e6e5e5573961207babd66d7c981504d118ed4d14e87f7d6a8ca4180904b9"
REQUIRED = {
    "00_RFC_TRIGGER_VERDICT.md",
    "01_BA12_LIVE_SOURCE_CONFLICT.json",
    "02_LEGACY_PATH_INVENTORY.json",
    "03_RFC_0007_STATUS.md",
    "04_CONFLICT_VERIFIER_RECEIPT.json",
    "05_SEMANTIC_WAVE_FREEZE_RECEIPT.json",
    "06_RFC0009_FREEZE_RECEIPT.json",
    "07_BA10_BA11_RFC0008_FREEZE_RECEIPTS.json",
    "08_PHASE_A_EVIDENCE_RECEIPT.json",
    "09_TARGETED_TEST_RECEIPT.json",
    "10_GIT_TREE_BINDINGS.json",
    "11_CHANGED_FILES_REPORT.json",
    "12_FOREIGN_WORKTREE_BOUNDARY.json",
    "13_HANDOFF_IDENTITY.json",
    "14_INDEPENDENT_RFC_DECISION_REQUIRED.md",
    "15_FINAL_STATE.json",
    "independent_verifier/verify_ba12_r3_live_source_rfc_trigger_evidence.py",
    "MANIFEST.json",
}


def manifest_hash(value: dict[str, Any]) -> str:
    body = {**value, "manifest_sha256": ""}
    return hashlib.sha256(DOMAIN + json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_package(package: Path) -> dict[str, Any]:
    package_bytes = package.read_bytes()
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if archive.testzip() is not None or len(names) != len(set(names)) or set(names) != REQUIRED:
            raise ValueError("BA12_R3_RFC_TRIGGER_MEMBER_SET_INVALID")
        if any((item.external_attr >> 16) & 0o777 != 0o644 for item in archive.infolist()):
            raise ValueError("BA12_R3_RFC_TRIGGER_MEMBER_MODE_INVALID")
        manifest = json.loads(archive.read("MANIFEST.json"))
        if manifest_hash(manifest) != manifest.get("manifest_sha256"):
            raise ValueError("BA12_R3_RFC_TRIGGER_MANIFEST_HASH_INVALID")
        rows = manifest.get("payloads", [])
        if [row["path"] for row in rows] != sorted(REQUIRED - {"MANIFEST.json"}):
            raise ValueError("BA12_R3_RFC_TRIGGER_MANIFEST_CLOSURE_INVALID")
        for row in rows:
            payload = archive.read(row["path"])
            if len(payload) != row["bytes"] or hashlib.sha256(payload).hexdigest() != row["sha256"]:
                raise ValueError("BA12_R3_RFC_TRIGGER_PAYLOAD_HASH_INVALID")
        conflict = json.loads(archive.read("01_BA12_LIVE_SOURCE_CONFLICT.json"))
        verifier = json.loads(archive.read("04_CONFLICT_VERIFIER_RECEIPT.json"))
        semantic = json.loads(archive.read("05_SEMANTIC_WAVE_FREEZE_RECEIPT.json"))
        rfc9 = json.loads(archive.read("06_RFC0009_FREEZE_RECEIPT.json"))
        dependencies = json.loads(archive.read("07_BA10_BA11_RFC0008_FREEZE_RECEIPTS.json"))
        phase_a = json.loads(archive.read("08_PHASE_A_EVIDENCE_RECEIPT.json"))
        targeted = json.loads(archive.read("09_TARGETED_TEST_RECEIPT.json"))
        changed = json.loads(archive.read("11_CHANGED_FILES_REPORT.json"))
        boundary = json.loads(archive.read("12_FOREIGN_WORKTREE_BOUNDARY.json"))
        state = json.loads(archive.read("15_FINAL_STATE.json"))
        if conflict.get("diagnostic_code") != DIAGNOSTIC or conflict.get("stop_conditions") != [2, 4]:
            raise ValueError("BA12_R3_RFC_TRIGGER_CONFLICT_INVALID")
        if verifier.get("status") != "PASS" or verifier.get("allowed_receipt_transport_values") != ["offline_fixture", "offline_replay"] or verifier.get("required_transport_value") != "live_acquisition":
            raise ValueError("BA12_R3_RFC_TRIGGER_VERIFIER_INVALID")
        if semantic.get("status") != "PASS" or semantic.get("version_lock_sha256") != SEMANTIC_FREEZE:
            raise ValueError("BA12_R3_RFC_TRIGGER_SEMANTIC_FREEZE_INVALID")
        if rfc9.get("status") != "PASS" or rfc9.get("freeze_sha256") != RFC9_FREEZE:
            raise ValueError("BA12_R3_RFC_TRIGGER_RFC9_FREEZE_INVALID")
        if any(row.get("status") != "PASS" for row in dependencies.get("receipts", [])):
            raise ValueError("BA12_R3_RFC_TRIGGER_DEPENDENCY_INVALID")
        if phase_a.get("status") != "PASS" or targeted.get("status") != "PASS":
            raise ValueError("BA12_R3_RFC_TRIGGER_RECEIPT_INVALID")
        if changed.get("runtime_code_changed") is not False or changed.get("product_changed") is not False or changed.get("frozen_file_changed") is not False:
            raise ValueError("BA12_R3_RFC_TRIGGER_CHANGE_SCOPE_INVALID")
        if boundary.get("status") != "PASS" or boundary.get("unchanged") is not True:
            raise ValueError("BA12_R3_RFC_TRIGGER_BOUNDARY_INVALID")
        required_false = ("ready_for_independent_rereview", "ba12_implementation_ready", "ba12_frozen", "release_ready_candidate", "release_ready", "release_authorized", "publication_authorized", "deploy_authorized")
        if state.get("diagnostic_code") != DIAGNOSTIC or any(state.get(key) is not False for key in required_false):
            raise ValueError("BA12_R3_RFC_TRIGGER_FINAL_STATE_INVALID")
    return {"contract_id": "room16.ba12.r3.live_source_rfc_trigger.evidence_verifier@1", "status": "PASS", "diagnostic_code": DIAGNOSTIC, "package": package.name, "package_bytes": len(package_bytes), "package_sha256": hashlib.sha256(package_bytes).hexdigest(), "zip_entries": len(names), "manifest_sha256": manifest["manifest_sha256"], "semantic_wave_freeze_sha256": SEMANTIC_FREEZE, "rfc0009_freeze_sha256": RFC9_FREEZE, "stop_conditions": [2, 4], "rfc_trigger_required": True, "ba12_implementation_ready": False, "ba12_frozen": False, "release_ready": False}


def main() -> int:
    print(json.dumps(verify_package(Path(sys.argv[1]).resolve()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
