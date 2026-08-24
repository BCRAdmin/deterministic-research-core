#!/usr/bin/env python3
"""Standalone verifier for RFC-0010 BA12 live-capture transport evidence."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

DOMAIN = b"room16.rfc0010.live_capture_transport.evidence_manifest@1\0"
BA3_CONTRACT_SHA256 = "c37dd7847905f9113e5b50af9ba669cebf06f1520c2099de65cb5e4ce16fda2b"
SEMANTIC_WAVE_LOCK = "62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9"
RFC0009_FREEZE = "e9c9e6e5e5573961207babd66d7c981504d118ed4d14e87f7d6a8ca4180904b9"
PRODUCT_HEAD = "6dc397556a1e66a1b6eb29a1b3070914b0d562ba"
REQUIRED = {
    "00_IMPLEMENTATION_VERDICT.md",
    "01_INDEPENDENT_RFC_DECISION.md",
    "02_BASELINE_LOCK.json",
    "03_RFC_0010.md",
    "04_LIVE_RETRIEVAL_RECEIPT_CONTRACT.json",
    "05_LIVE_CAPTURE_ARTIFACT_CONTRACT.json",
    "06_LIVE_CAPTURE_BINDING_CONTRACT.json",
    "07_LIVE_CAPTURE_SET_CONTRACT.json",
    "08_FROZEN_BA3_BRIDGE_REPORT.json",
    "09_PROVIDER_POLICY_COST_REPORT.json",
    "10_TIME_LOOKAHEAD_REPORT.json",
    "11_RECOVERY_CONCURRENCY_REPORT.json",
    "12_PROVIDER_ADAPTER_HARNESS_REPORT.json",
    "13_ACCEPTANCE_MATRIX_EXECUTED.json",
    "14_SEMANTIC_WAVE_FREEZE_REGRESSION.json",
    "15_BA10_BA11_RFC0008_RFC0009_REGRESSION.json",
    "16_FULL_REGRESSION_RECEIPTS.json",
    "17_SOURCE_TREE_BINDINGS.json",
    "18_CHANGED_FILES.json",
    "19_PRODUCT_UNCHANGED_REPORT.json",
    "20_FOREIGN_WORKTREE_BOUNDARY_REPORT.json",
    "21_DETERMINISTIC_BUILD_REPORT.json",
    "22_INDEPENDENT_REREVIEW_REQUEST.md",
    "23_IMPLEMENTATION_PATCH.patch",
    "MANIFEST.json",
    "independent_verifier/VERIFIER_RECEIPT.json",
    "independent_verifier/verify_rfc0010_live_capture_evidence.py",
}


def manifest_hash(value: dict[str, Any]) -> str:
    body = {**value, "manifest_sha256": ""}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(DOMAIN + encoded).hexdigest()


def self_test() -> dict[str, object]:
    fixture = {
        "contract_id": "room16.rfc0010.live_capture_transport.evidence_manifest@1",
        "schema_version": 1,
        "payloads": [],
        "manifest_sha256": "",
    }
    first = manifest_hash(fixture)
    fixture["schema_version"] = 2
    second = manifest_hash(fixture)
    if first == second or len(first) != 64:
        raise ValueError("RFC10_VERIFIER_SELF_TEST_FAILED")
    return {
        "contract_id": "room16.rfc0010.evidence_verifier_self_test@1",
        "status": "PASS",
    }


def _json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    value = json.loads(archive.read(name))
    if not isinstance(value, dict):
        raise ValueError(f"RFC10_EVIDENCE_JSON_OBJECT_REQUIRED:{name}")
    return value


def verify_package(package: Path) -> dict[str, Any]:
    package_bytes = package.read_bytes()
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or not REQUIRED <= set(names):
            raise ValueError("RFC10_EVIDENCE_MEMBER_SET_INVALID")
        if any((item.external_attr >> 16) & 0o777 != 0o644 for item in archive.infolist()):
            raise ValueError("RFC10_EVIDENCE_MEMBER_MODE_INVALID")
        manifest = _json(archive, "MANIFEST.json")
        if manifest_hash(manifest) != manifest.get("manifest_sha256"):
            raise ValueError("RFC10_EVIDENCE_MANIFEST_HASH_INVALID")
        records = manifest.get("payloads")
        if not isinstance(records, list) or [item["path"] for item in records] != sorted(
            set(names) - {"MANIFEST.json"}
        ):
            raise ValueError("RFC10_EVIDENCE_MANIFEST_CLOSURE_INVALID")
        for item in records:
            payload = archive.read(item["path"])
            if len(payload) != item["bytes"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
                raise ValueError("RFC10_EVIDENCE_PAYLOAD_HASH_INVALID")

        baseline = _json(archive, "02_BASELINE_LOCK.json")
        live_schema = _json(archive, "04_LIVE_RETRIEVAL_RECEIPT_CONTRACT.json")
        artifact_schema = _json(archive, "05_LIVE_CAPTURE_ARTIFACT_CONTRACT.json")
        binding_schema = _json(archive, "06_LIVE_CAPTURE_BINDING_CONTRACT.json")
        set_schema = _json(archive, "07_LIVE_CAPTURE_SET_CONTRACT.json")
        bridge = _json(archive, "08_FROZEN_BA3_BRIDGE_REPORT.json")
        provider = _json(archive, "09_PROVIDER_POLICY_COST_REPORT.json")
        time_report = _json(archive, "10_TIME_LOOKAHEAD_REPORT.json")
        recovery = _json(archive, "11_RECOVERY_CONCURRENCY_REPORT.json")
        adapters = _json(archive, "12_PROVIDER_ADAPTER_HARNESS_REPORT.json")
        matrix = _json(archive, "13_ACCEPTANCE_MATRIX_EXECUTED.json")
        semantic = _json(archive, "14_SEMANTIC_WAVE_FREEZE_REGRESSION.json")
        freezes = _json(archive, "15_BA10_BA11_RFC0008_RFC0009_REGRESSION.json")
        regressions = _json(archive, "16_FULL_REGRESSION_RECEIPTS.json")
        bindings = _json(archive, "17_SOURCE_TREE_BINDINGS.json")
        changed = _json(archive, "18_CHANGED_FILES.json")
        product = _json(archive, "19_PRODUCT_UNCHANGED_REPORT.json")
        foreign = _json(archive, "20_FOREIGN_WORKTREE_BOUNDARY_REPORT.json")
        deterministic = _json(archive, "21_DETERMINISTIC_BUILD_REPORT.json")
        embedded = _json(archive, "independent_verifier/VERIFIER_RECEIPT.json")

        if (
            baseline.get("ba3_source_contract_file_sha256") != BA3_CONTRACT_SHA256
            or baseline.get("semantic_wave_version_lock_sha256") != SEMANTIC_WAVE_LOCK
            or baseline.get("rfc0009_freeze_sha256") != RFC0009_FREEZE
            or baseline.get("product", {}).get("commit") != PRODUCT_HEAD
        ):
            raise ValueError("RFC10_EVIDENCE_BASELINE_INVALID")
        schema_contracts = (
            (live_schema, "room16.ba12.live_retrieval_receipt"),
            (artifact_schema, "room16.ba12.live_capture_artifact"),
            (binding_schema, "room16.ba12.live_capture_binding"),
            (set_schema, "room16.ba12.live_capture_set"),
        )
        for schema, contract_id in schema_contracts:
            contract = schema.get("properties", {}).get("contract_id", {}).get("const")
            if contract != contract_id or schema.get("additionalProperties") is not False:
                raise ValueError("RFC10_EVIDENCE_CONTRACT_SCHEMA_INVALID")
        if (
            bridge.get("status") != "PASS"
            or bridge.get("ba3_contract_sha256") != BA3_CONTRACT_SHA256
            or bridge.get("ba3_transport") != "offline_replay"
            or bridge.get("semantic_wave_changed") is not False
            or provider.get("status") != "PASS"
            or time_report.get("status") != "PASS"
            or recovery.get("status") != "PASS"
            or adapters.get("status") != "PASS"
            or sorted(adapters.get("providers", [])) != ["bse", "massive", "nasdaq", "sec"]
        ):
            raise ValueError("RFC10_EVIDENCE_LIVE_TRANSPORT_REPORT_INVALID")
        rows = matrix.get("rows")
        expected_ids = [f"RFC10-T-{number:03d}" for number in range(1, 48)]
        if (
            matrix.get("row_count") != 47
            or not isinstance(rows, list)
            or [row.get("test_id") for row in rows] != expected_ids
            or any(row.get("actual") != row.get("expected") for row in rows)
        ):
            raise ValueError("RFC10_EVIDENCE_MATRIX_INVALID")
        if semantic.get("status") != "PASS" or semantic.get("version_lock_sha256") != SEMANTIC_WAVE_LOCK:
            raise ValueError("RFC10_EVIDENCE_SEMANTIC_FREEZE_INVALID")
        if freezes.get("status") != "PASS" or any(
            receipt.get("status") != "PASS" for receipt in freezes.get("receipts", [])
        ):
            raise ValueError("RFC10_EVIDENCE_DEPENDENCY_FREEZE_INVALID")
        if any(receipt.get("status") != "PASS" for receipt in regressions.get("receipts", [])):
            raise ValueError("RFC10_EVIDENCE_FULL_REGRESSION_INVALID")
        if (
            bindings.get("research", {}).get("origin")
            != "https://github.com/BCRAdmin/deterministic-research-core.git"
            or bindings.get("product", {}).get("origin")
            != "https://github.com/BCRAdmin/company-dossier-lab.git"
            or changed.get("scope_valid") is not True
            or changed.get("frozen_files_changed")
            or changed.get("private_secret_markers_found")
            or product.get("status") != "PASS"
            or product.get("head") != PRODUCT_HEAD
            or product.get("changed") is not False
            or foreign.get("status") != "PASS"
            or foreign.get("unchanged") is not True
            or deterministic.get("byte_identical_builds") is not True
            or embedded.get("status") != "PASS"
        ):
            raise ValueError("RFC10_EVIDENCE_SCOPE_OR_BOUNDARY_INVALID")
        verdict = archive.read("00_IMPLEMENTATION_VERDICT.md")
        required_markers = (
            b"ready_for_independent_rereview=true",
            b"rfc0010_implementation_ready=false",
            b"rfc0010_frozen=false",
            b"ba12_resume_authorized=false",
        )
        if any(marker not in verdict for marker in required_markers):
            raise ValueError("RFC10_EVIDENCE_FINAL_STATE_INVALID")
        private_markers = (
            b"-----BEGIN " + b"PRIVATE KEY-----",
            b"OPENSSH " + b"PRIVATE KEY",
            b"gh" + b"p_",
        )
        for name in names:
            if name == "18_CHANGED_FILES.json":
                continue
            payload = archive.read(name)
            if any(marker in payload for marker in private_markers):
                raise ValueError("RFC10_EVIDENCE_PRIVATE_SECRET_MARKER")
    return {
        "ba12_resume_authorized": False,
        "contract_id": "room16.rfc0010.live_capture_transport.evidence_verifier@1",
        "manifest_sha256": manifest["manifest_sha256"],
        "matrix_rows_passed": 47,
        "package": package.name,
        "package_bytes": len(package_bytes),
        "package_sha256": hashlib.sha256(package_bytes).hexdigest(),
        "ready_for_independent_rereview": True,
        "rfc0010_frozen": False,
        "rfc0010_implementation_ready": False,
        "status": "PASS",
        "zip_entries": len(names),
    }


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        result = self_test()
    elif len(sys.argv) == 2:
        result = verify_package(Path(sys.argv[1]).resolve())
    else:
        raise SystemExit("usage: verify_rfc0010_live_capture_evidence.py PACKAGE|--self-test")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
