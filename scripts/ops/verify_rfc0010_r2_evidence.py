#!/usr/bin/env python3
"""Standalone verifier for RFC-0010 R2 durable-recovery evidence."""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

DOMAIN = b"room16.rfc0010.r2_evidence_manifest@1\0"
BA3_CONTRACT_SHA256 = "c37dd7847905f9113e5b50af9ba669cebf06f1520c2099de65cb5e4ce16fda2b"
SEMANTIC_WAVE_LOCK = "62867ad72cd1a99eee482e75087cbe01449faa650d7cf2c535fd494c5fef30f9"
R1_EVIDENCE = "139121a0486df417d6af82953de11be2c54f1a75"
PRODUCT_HEAD = "6dc397556a1e66a1b6eb29a1b3070914b0d562ba"
SOURCE_HANDOFF_SHA256 = "25296b0ce3a1accb261520b0160e8636b21f0a8a8e4e4ef8adba87f315b3b173"
REQUIRED = {
    "00_R2_IMPLEMENTATION_VERDICT.md",
    "01_R2_FINDINGS.json",
    "02_BASELINE_LOCK.json",
    "03_RFC_0010_R2_DELTA.md",
    "04_DURABLE_ATTEMPT_CONTRACT.json",
    "05_PROVIDER_SUCCESS_FAILURE_CONTRACT.json",
    "06_PERSISTED_GRAPH_RECOVERY_REPORT.json",
    "07_PROCESS_RESTART_RECOVERY_REPORT.json",
    "08_PROVIDER_STATUS_REPORT.json",
    "09_REAL_ADAPTER_HARNESS_REPORT.json",
    "10_FROZEN_BA3_BRIDGE_REPORT.json",
    "11_R2_ACCEPTANCE_MATRIX_EXECUTED.json",
    "12_R1_REGRESSION_MATRIX.json",
    "13_SEMANTIC_WAVE_BA10_BA11_RFC8_RFC9_REGRESSION.json",
    "14_FULL_REGRESSION_RECEIPTS.json",
    "15_SOURCE_TREE_BINDINGS.json",
    "16_CHANGED_FILES_PER_FINDING.json",
    "17_PRODUCT_UNCHANGED_REPORT.json",
    "18_FOREIGN_WORKTREE_BOUNDARY_REPORT.json",
    "19_DETERMINISTIC_BUILD_REPORT.json",
    "20_INDEPENDENT_REREVIEW_REQUEST.md",
    "21_IMPLEMENTATION_PATCH.patch",
    "MANIFEST.json",
    "independent_verifier/VERIFIER_RECEIPT.json",
    "independent_verifier/verify_rfc0010_r2_evidence.py",
}


def manifest_hash(value: dict[str, Any]) -> str:
    body = {**value, "manifest_sha256": ""}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(DOMAIN + encoded).hexdigest()


def self_test() -> dict[str, object]:
    value = {
        "contract_id": "room16.rfc0010.r2_evidence_manifest@1",
        "schema_version": 1,
        "payloads": [],
        "manifest_sha256": "",
    }
    first = manifest_hash(value)
    value["schema_version"] = 2
    if first == manifest_hash(value) or len(first) != 64:
        raise ValueError("RFC10_R2_VERIFIER_SELF_TEST_FAILED")
    return {"contract_id": "room16.rfc0010.r2_verifier_self_test@1", "status": "PASS"}


def _json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    value = json.loads(archive.read(name))
    if not isinstance(value, dict):
        raise ValueError(f"RFC10_R2_JSON_OBJECT_REQUIRED:{name}")
    return value


def verify_package(package: Path) -> dict[str, Any]:
    package_bytes = package.read_bytes()
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        if set(names) != REQUIRED or len(names) != len(set(names)):
            raise ValueError("RFC10_R2_MEMBER_SET_INVALID")
        if any((item.external_attr >> 16) & 0o777 != 0o644 for item in archive.infolist()):
            raise ValueError("RFC10_R2_MEMBER_MODE_INVALID")
        manifest = _json(archive, "MANIFEST.json")
        if manifest_hash(manifest) != manifest.get("manifest_sha256"):
            raise ValueError("RFC10_R2_MANIFEST_HASH_INVALID")
        records = manifest.get("payloads")
        if not isinstance(records, list) or [item.get("path") for item in records] != sorted(
            REQUIRED - {"MANIFEST.json"}
        ):
            raise ValueError("RFC10_R2_MANIFEST_CLOSURE_INVALID")
        for item in records:
            payload = archive.read(item["path"])
            if len(payload) != item.get("bytes") or hashlib.sha256(payload).hexdigest() != item.get(
                "sha256"
            ):
                raise ValueError("RFC10_R2_PAYLOAD_HASH_INVALID")

        findings = _json(archive, "01_R2_FINDINGS.json")
        baseline = _json(archive, "02_BASELINE_LOCK.json")
        attempt_schema = _json(archive, "04_DURABLE_ATTEMPT_CONTRACT.json")
        provider_contract = _json(archive, "05_PROVIDER_SUCCESS_FAILURE_CONTRACT.json")
        graph = _json(archive, "06_PERSISTED_GRAPH_RECOVERY_REPORT.json")
        restart = _json(archive, "07_PROCESS_RESTART_RECOVERY_REPORT.json")
        status = _json(archive, "08_PROVIDER_STATUS_REPORT.json")
        adapters = _json(archive, "09_REAL_ADAPTER_HARNESS_REPORT.json")
        bridge = _json(archive, "10_FROZEN_BA3_BRIDGE_REPORT.json")
        matrix = _json(archive, "11_R2_ACCEPTANCE_MATRIX_EXECUTED.json")
        r1 = _json(archive, "12_R1_REGRESSION_MATRIX.json")
        freezes = _json(archive, "13_SEMANTIC_WAVE_BA10_BA11_RFC8_RFC9_REGRESSION.json")
        regressions = _json(archive, "14_FULL_REGRESSION_RECEIPTS.json")
        bindings = _json(archive, "15_SOURCE_TREE_BINDINGS.json")
        changed = _json(archive, "16_CHANGED_FILES_PER_FINDING.json")
        product = _json(archive, "17_PRODUCT_UNCHANGED_REPORT.json")
        foreign = _json(archive, "18_FOREIGN_WORKTREE_BOUNDARY_REPORT.json")
        deterministic = _json(archive, "19_DETERMINISTIC_BUILD_REPORT.json")
        embedded = _json(archive, "independent_verifier/VERIFIER_RECEIPT.json")

        if findings.get("counts") != {"P0": 2, "P1": 2, "total": 4}:
            raise ValueError("RFC10_R2_FINDINGS_INVALID")
        if (
            baseline.get("contract_id") != "room16.rfc0010.r2_baseline_lock@1"
            or baseline.get("research", {}).get("evidence_successor_commit") != R1_EVIDENCE
            or baseline.get("product", {}).get("commit") != PRODUCT_HEAD
            or baseline.get("ba3_contract_sha256") != BA3_CONTRACT_SHA256
            or baseline.get("semantic_wave_v1_lock") != SEMANTIC_WAVE_LOCK
        ):
            raise ValueError("RFC10_R2_BASELINE_INVALID")
        if (
            manifest.get("source_handoff_sha256") != SOURCE_HANDOFF_SHA256
            or attempt_schema.get("properties", {}).get("contract_id", {}).get("const")
            != "room16.ba12.live_attempt_record"
            or attempt_schema.get("additionalProperties") is not False
            or provider_contract.get("raw_status_hash_bound") is not True
            or provider_contract.get("normalized_outcome_hash_bound") is not True
        ):
            raise ValueError("RFC10_R2_CONTRACT_INVALID")
        if (
            graph.get("status") != "PASS"
            or graph.get("binding_persisted") is not True
            or graph.get("capture_set_persisted") is not True
            or graph.get("ba3_snapshot_persisted") is not True
            or restart.get("status") != "PASS"
            or restart.get("disk_only") is not True
            or restart.get("old_provider_response_required") is not False
            or status.get("status") != "PASS"
            or status.get("error_payload_can_be_source") is not False
            or adapters.get("status") != "PASS"
            or sorted(adapters.get("providers", [])) != ["bse", "massive", "nasdaq", "sec"]
        ):
            raise ValueError("RFC10_R2_CLOSURE_REPORT_INVALID")
        if (
            bridge.get("status") != "PASS"
            or bridge.get("ba3_contract_sha256") != BA3_CONTRACT_SHA256
            or bridge.get("transport") != "offline_replay"
            or bridge.get("semantic_wave_changed") is not False
        ):
            raise ValueError("RFC10_R2_BRIDGE_INVALID")
        rows = matrix.get("rows")
        expected_ids = [f"RFC10-R2-T-{number:03d}" for number in range(1, 38)]
        if (
            matrix.get("row_count") != 37
            or not isinstance(rows, list)
            or [row.get("test_id") for row in rows] != expected_ids
            or any(row.get("actual") != row.get("expected") for row in rows)
            or any(not str(row.get("node_id", "")).startswith("research_agent/tests/") for row in rows)
        ):
            raise ValueError("RFC10_R2_MATRIX_INVALID")
        if r1.get("row_count") != 47 or r1.get("status") != "PASS":
            raise ValueError("RFC10_R2_R1_REGRESSION_INVALID")
        if freezes.get("status") != "PASS" or any(
            item.get("status") != "PASS" for item in freezes.get("receipts", [])
        ):
            raise ValueError("RFC10_R2_FREEZE_INVALID")
        if any(item.get("status") != "PASS" for item in regressions.get("receipts", [])):
            raise ValueError("RFC10_R2_REGRESSION_INVALID")
        if (
            bindings.get("research", {}).get("origin")
            != "https://github.com/BCRAdmin/deterministic-research-core.git"
            or bindings.get("product", {}).get("origin")
            != "https://github.com/BCRAdmin/company-dossier-lab.git"
            or changed.get("scope_valid") is not True
            or changed.get("frozen_files_changed")
            or changed.get("private_secret_markers_found")
            or product.get("status") != "PASS"
            or product.get("changed") is not False
            or product.get("head") != PRODUCT_HEAD
            or foreign.get("status") != "PASS"
            or foreign.get("unchanged") is not True
            or deterministic.get("byte_identical_builds") is not True
            or embedded.get("status") != "PASS"
        ):
            raise ValueError("RFC10_R2_SCOPE_OR_BOUNDARY_INVALID")
        verdict = archive.read("00_R2_IMPLEMENTATION_VERDICT.md")
        markers = (
            b"ready_for_independent_rereview=true",
            b"rfc0010_implementation_ready=false",
            b"rfc0010_frozen=false",
            b"ba12_resume_authorized=false",
            b"release_authorized=false",
            b"publication_authorized=false",
            b"deploy_authorized=false",
        )
        if any(marker not in verdict for marker in markers):
            raise ValueError("RFC10_R2_FINAL_STATE_INVALID")
        private_markers = (
            b"-----BEGIN " + b"PRIVATE KEY-----",
            b"OPENSSH " + b"PRIVATE KEY",
            b"gh" + b"p_",
        )
        for name in names:
            if name == "16_CHANGED_FILES_PER_FINDING.json":
                continue
            if any(marker in archive.read(name) for marker in private_markers):
                raise ValueError("RFC10_R2_PRIVATE_SECRET_MARKER")
    return {
        "ba12_resume_authorized": False,
        "contract_id": "room16.rfc0010.r2_evidence_verifier@1",
        "manifest_sha256": manifest["manifest_sha256"],
        "matrix_rows_passed": 37,
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
        raise SystemExit("usage: verify_rfc0010_r2_evidence.py PACKAGE|--self-test")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
