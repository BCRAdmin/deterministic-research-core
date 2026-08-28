#!/usr/bin/env python3
"""Standalone verifier for a Fixed24 execution-authority closure result ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import PurePosixPath
from typing import Any


REQUIRED = {
    "00_VERDICT.md",
    "01_STOP_RESULT_BINDING.json",
    "02_EXECUTION_AUTHORITY_CONTRACT.json",
    "03_CHANGED_FILES.json",
    "04_SEMANTIC_IMMUTABILITY_PROOF.json",
    "05_ORCL_PREFLIGHT_FIXTURE.json",
    "06_POSITIVE_AUTHORIZATION_FIXTURES.json",
    "07_NEGATIVE_AUTHORIZATION_FIXTURES.json",
    "08_PRENETWORK_NONINTERFERENCE.json",
    "09_RUNNER_INTEGRATION_REPORT.json",
    "10_AUTHORITY_MATRIX_EXECUTED.json",
    "11_R1_R4_REGRESSION.json",
    "12_EIGHT_ALPHA_REGRESSION.json",
    "13_FULL_RESEARCH_REGRESSION.json",
    "14_FULL_PRODUCT_REGRESSION.json",
    "15_WHOLE_ALPHA_REGRESSION.json",
    "16_SECURITY_DEPENDENCY_REPORT.json",
    "17_BOUNDARY_GATE_V2_REPORT.json",
    "18_FIXED24_NONINTERFERENCE.json",
    "19_REPOSITORY_END_STATE.json",
    "20_BATCH_RESTART_READINESS.json",
    "21_INDEPENDENT_REREVIEW_REQUEST.md",
    "MANIFEST.json",
    "SHA256SUMS.txt",
    "independent_verifier/VERIFIER_RECEIPT.json",
    "independent_verifier/verify_authority_closure.py",
}


def _canonical_sha(value: dict[str, Any], omitted: str) -> str:
    body = dict(value)
    body.pop(omitted, None)
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def verify(archive_path: str) -> dict[str, object]:
    failures: list[str] = []
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            failures.append("duplicate_zip_entries")
        if any(PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts for name in names):
            failures.append("unsafe_zip_path")
        if not REQUIRED.issubset(names):
            failures.append("required_files_missing")
        manifest = json.loads(archive.read("MANIFEST.json"))
        if manifest.get("manifest_sha256") != _canonical_sha(manifest, "manifest_sha256"):
            failures.append("manifest_selfhash")
        files = manifest.get("files", [])
        if manifest.get("file_count") != len(files):
            failures.append("manifest_file_count")
        for item in files:
            path = item["path"]
            if path not in names:
                failures.append(f"manifest_missing:{path}")
                continue
            payload = archive.read(path)
            if len(payload) != item["bytes"]:
                failures.append(f"manifest_bytes:{path}")
            if hashlib.sha256(payload).hexdigest() != item["sha256"]:
                failures.append(f"manifest_sha256:{path}")
        matrix = json.loads(archive.read("10_AUTHORITY_MATRIX_EXECUTED.json"))
        if (
            matrix.get("status") != "PASS"
            or matrix.get("row_count") != 30
            or matrix.get("passed_count") != 30
            or matrix.get("failed_count") != 0
            or matrix.get("live_network_query_count") != 0
            or matrix.get("completed_case_count") != 0
        ):
            failures.append("authority_matrix")
        orcl = json.loads(archive.read("05_ORCL_PREFLIGHT_FIXTURE.json"))
        if (
            orcl.get("status") != "PASS"
            or orcl.get("ticker") != "ORCL"
            or orcl.get("sequence") != 1
            or orcl.get("authorization_mode") != "PREFLIGHT_ONLY"
            or orcl.get("network_queries") != 0
        ):
            failures.append("orcl_preflight")
        immutability = json.loads(archive.read("04_SEMANTIC_IMMUTABILITY_PROOF.json"))
        if (
            immutability.get("status") != "PASS"
            or immutability.get("semantic_runtime_unchanged") is not True
            or immutability.get("product_changed") is not False
        ):
            failures.append("semantic_immutability")
        noninterference = json.loads(archive.read("18_FIXED24_NONINTERFERENCE.json"))
        if any(
            noninterference.get(field) != 0
            for field in (
                "fixed24_queries",
                "fixed24_runs",
                "case_attempt_count",
                "completed_case_count",
            )
        ) or noninterference.get("batch_started") is not False:
            failures.append("fixed24_noninterference")
        readiness = json.loads(archive.read("20_BATCH_RESTART_READINESS.json"))
        expected_state = {
            "execution_authority_candidate_ready": True,
            "ORCL_preflight_authorized": True,
            "ORCL_network_queries": 0,
            "fixed24_queries": 0,
            "fixed24_runs": 0,
            "semantic_runtime_unchanged": True,
            "product_changed": False,
            "batch_started": False,
            "ready_for_independent_rereview": True,
        }
        if any(readiness.get(key) != value for key, value in expected_state.items()):
            failures.append("candidate_state")
        boundary = json.loads(archive.read("17_BOUNDARY_GATE_V2_REPORT.json"))
        if boundary.get("verdict") != "PASS" or boundary.get("room16_foreign_mutation") is not False:
            failures.append("boundary_gate")
        result = {
            "status": "PASS" if not failures else "FAIL",
            "manifest_sha256": manifest.get("manifest_sha256"),
            "payload_count": len(files),
            "matrix_rows": matrix.get("row_count"),
            "fixed24_queries": noninterference.get("fixed24_queries"),
            "fixed24_runs": noninterference.get("fixed24_runs"),
            "failures": failures,
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive")
    args = parser.parse_args()
    result = verify(args.archive)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
