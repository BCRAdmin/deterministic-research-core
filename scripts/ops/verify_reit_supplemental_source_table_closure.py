#!/usr/bin/env python3
"""Standalone verifier for the REIT supplemental source/table closure result."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any


REQUIRED = tuple(
    f"{index:02d}_{name}"
    for index, name in enumerate(
        (
            "VERDICT.md",
            "PRIOR_RESULT_BINDING.json",
            "BEFORE_DEFECT_REPRODUCTION.json",
            "SEC_FILING_INTENT_CONTRACT.json",
            "ITEM202_PARENT_SELECTION_REPORT.json",
            "SELECTION_CONTEXT_V2.json",
            "REXR_DISPOSITION_NEGATIVE_REGRESSION.json",
            "HIERARCHICAL_HEADER_POLICY.json",
            "EGP_HEADER_BEFORE_AFTER.json",
            "FFO_TOTAL_ROW_POLICY.json",
            "FFO_ROW_SAFETY_REGRESSION.json",
            "EXISTING_CAPTURE_OFFLINE_PROOF.json",
            "WAVE2_PRESTART_FREEZE.json",
            "WAVE2_RUN_LEDGER.json",
            "WAVE2_SOURCE_SELECTION.json",
            "WAVE2_FFO_FAMILY_RESULTS.json",
            "WAVE2_LIVE_VS_REPLAY.json",
            "REIT_CORE_SLOT_WAVE2_COMPANY_MATRIX.json",
            "REIT_CORE_SLOT_WAVE2_METRICS.json",
            "FIXED24_COMBINED_DEVELOPMENT_EVALUATION.json",
            "HOLDOUT12_BINDING.json",
            "HOLDOUT12_NONINTERFERENCE.json",
            "ACCEPTANCE_MATRIX_EXECUTED.json",
            "FULL_RESEARCH_REGRESSION.json",
            "FULL_PRODUCT_REGRESSION.json",
            "PRIOR_ALPHA_SHARED_REGRESSION.json",
            "SECURITY_DEPENDENCY_REPORT.json",
            "BOUNDARY_GATE_V2_REPORT.json",
            "REPOSITORY_END_STATE.json",
            "REIT_SHARED_CLOSURE_FREEZE_CANDIDATE.json",
            "INDEPENDENT_REREVIEW_REQUEST.md",
        )
    )
)
EXPECTED_DEV6 = ("AMT", "EQIX", "PSA", "CUBE", "EGP", "REXR")
EXPECTED_PARENTS = {
    "AMT": "0001053507-26-000131",
    "EQIX": "0001101239-26-000145",
    "PSA": "0001628280-26-050608",
    "CUBE": "0001298675-26-000035",
    "EGP": "0000049600-26-000040",
    "REXR": "0001571283-26-000037",
}
HOLDOUT_SHA = "4fa4c0171f098d59b206cd270e60fb497800aa152d63cca66290aee35e6a5b7f"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify(root: Path) -> dict[str, object]:
    extra_required = (
        "MANIFEST.json",
        "SHA256SUMS.txt",
        "independent_verifier/verify_reit_source_table_closure.py",
        "independent_verifier/VERIFIER_RECEIPT.json",
    )
    missing = [name for name in (*REQUIRED, *extra_required) if not (root / name).is_file()]
    if missing:
        raise RuntimeError(f"REIT_SOURCE_TABLE_REQUIRED_FILES_MISSING:{missing}")
    for directory in ("companies_wave2", "source_review"):
        if not (root / directory).is_dir():
            raise RuntimeError(f"REIT_SOURCE_TABLE_REQUIRED_DIRECTORY_MISSING:{directory}")

    manifest = _json(root / "MANIFEST.json")
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    if hashlib.sha256(canonical).hexdigest() != manifest["manifest_sha256"]:
        raise RuntimeError("REIT_SOURCE_TABLE_MANIFEST_SELFHASH_MISMATCH")
    for item in manifest["files"]:
        path = root / item["path"]
        if (
            not path.is_file()
            or path.stat().st_size != item["bytes"]
            or _sha(path) != item["sha256"]
        ):
            raise RuntimeError(f"REIT_SOURCE_TABLE_PAYLOAD_MISMATCH:{item['path']}")
    sums = {}
    for line in (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        sums[relative] = digest
    for relative, digest in sums.items():
        if not (root / relative).is_file() or _sha(root / relative) != digest:
            raise RuntimeError(f"REIT_SOURCE_TABLE_CHECKSUM_MISMATCH:{relative}")

    ledger = _json(root / "13_WAVE2_RUN_LEDGER.json")
    cases = ledger["cases"]
    if tuple(item["ticker"] for item in cases) != EXPECTED_DEV6:
        raise RuntimeError("REIT_SOURCE_TABLE_WAVE2_ORDER_MISMATCH")
    if any(item["status"] != "COMPLETE" for item in cases):
        raise RuntimeError("REIT_SOURCE_TABLE_WAVE2_INCOMPLETE")
    if ledger["fixed24_non_reit_live_queries"] != 0 or ledger["holdout12_queries"] != 0:
        raise RuntimeError("REIT_SOURCE_TABLE_FORBIDDEN_QUERY")

    parent_report = _json(root / "04_ITEM202_PARENT_SELECTION_REPORT.json")
    actual_parents = {item["ticker"]: item["selected_accession"] for item in parent_report["cases"]}
    if actual_parents != EXPECTED_PARENTS:
        raise RuntimeError("REIT_SOURCE_TABLE_ITEM202_PARENT_MISMATCH")
    if parent_report["maximum_index_requests_per_issuer"] > 2:
        raise RuntimeError("REIT_SOURCE_TABLE_ITEM202_BUDGET_EXCEEDED")

    matrix = _json(root / "22_ACCEPTANCE_MATRIX_EXECUTED.json")
    if matrix["row_count"] != 53 or matrix["required_pass_count"] != 53:
        raise RuntimeError("REIT_SOURCE_TABLE_ACCEPTANCE_MATRIX_INCOMPLETE")
    if any(item["status"] != "PASS" for item in matrix["rows"]):
        raise RuntimeError("REIT_SOURCE_TABLE_ACCEPTANCE_MATRIX_FAILURE")

    holdout = _json(root / "21_HOLDOUT12_NONINTERFERENCE.json")
    if holdout["list_sha256"] != HOLDOUT_SHA or any(
        holdout[key] != 0 for key in ("queries", "discovery", "captures", "runs")
    ):
        raise RuntimeError("REIT_SOURCE_TABLE_HOLDOUT_INTERFERENCE")
    freeze = _json(root / "29_REIT_SHARED_CLOSURE_FREEZE_CANDIDATE.json")
    if freeze["ready_for_independent_rereview"] is not True:
        raise RuntimeError("REIT_SOURCE_TABLE_FREEZE_NOT_READY")
    if freeze["product_changed"] is not False or freeze["holdout12_live"] is not False:
        raise RuntimeError("REIT_SOURCE_TABLE_FORBIDDEN_STATE")
    for name in (
        "23_FULL_RESEARCH_REGRESSION.json",
        "24_FULL_PRODUCT_REGRESSION.json",
        "25_PRIOR_ALPHA_SHARED_REGRESSION.json",
        "26_SECURITY_DEPENDENCY_REPORT.json",
        "27_BOUNDARY_GATE_V2_REPORT.json",
    ):
        if _json(root / name).get("status") != "PASS":
            raise RuntimeError(f"REIT_SOURCE_TABLE_GATE_NOT_PASS:{name}")
    return {
        "status": "PASS",
        "manifest_sha256": manifest["manifest_sha256"],
        "payload_count": manifest["file_count"],
        "matrix_rows": matrix["row_count"],
        "wave2_cases": len(cases),
        "holdout12_queries": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    if args.artifact.is_dir():
        result = _verify(args.artifact)
    else:
        with tempfile.TemporaryDirectory(prefix="room16-reit-source-table-result.") as temporary:
            root = Path(temporary)
            with zipfile.ZipFile(args.artifact) as archive:
                if any(
                    Path(name).is_absolute() or ".." in Path(name).parts
                    for name in archive.namelist()
                ):
                    raise RuntimeError("REIT_SOURCE_TABLE_UNSAFE_ZIP_PATH")
                archive.extractall(root)
            result = _verify(root)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
