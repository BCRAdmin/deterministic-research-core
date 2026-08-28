#!/usr/bin/env python3
"""Standalone verifier for the Room16 REIT core-model R1 result bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any


REQUIRED = tuple(f"{index:02d}_{name}" for index, name in enumerate((
    "VERDICT.md",
    "PRIOR_CORRECTION_BINDING.json",
    "REIT_CORE_SLOT_POLICY_V2.json",
    "GENERIC_CORE_SLOT_CONTRACT.json",
    "ARCHETYPE_CORE_SLOT_REGISTRY.json",
    "REIT_OPERATING_MEASURE_POLICY.json",
    "REIT_SAFETY_REGRESSION.json",
    "REIT_DEV6_PRESTART_FREEZE.json",
    "REIT_DEV6_RUN_LEDGER.json",
    "REIT_DEV6_SOURCE_SELECTION.json",
    "REIT_DEV6_FFO_FAMILY_RESULTS.json",
    "REIT_DEV6_LIVE_VS_REPLAY.json",
    "FIXED24_ORIGINAL_FAIL_BINDING.json",
    "FIXED24_CORE_SLOT_V2_COMPANY_MATRIX.json",
    "FIXED24_CORE_SLOT_V2_ARCHETYPE_METRICS.json",
    "FIXED24_CORE_SLOT_V2_EVALUATION.json",
    "HOLDOUT12_LIST_BINDING.json",
    "HOLDOUT12_FUTURE_THRESHOLDS.json",
    "HOLDOUT12_NONINTERFERENCE.json",
    "FULL_RESEARCH_REGRESSION.json",
    "FULL_PRODUCT_REGRESSION.json",
    "PRIOR_ALPHA_SHARED_REGRESSION.json",
    "SECURITY_DEPENDENCY_REPORT.json",
    "BOUNDARY_GATE_V2_REPORT.json",
    "REPOSITORY_END_STATE.json",
    "REIT_CORE_MODEL_FREEZE_CANDIDATE.json",
    "INDEPENDENT_REREVIEW_REQUEST.md",
)))
EXPECTED_DEV6 = ("AMT", "EQIX", "PSA", "CUBE", "EGP", "REXR")
HOLDOUT_SHA = "4fa4c0171f098d59b206cd270e60fb497800aa152d63cca66290aee35e6a5b7f"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify(root: Path) -> dict[str, object]:
    missing = [name for name in (*REQUIRED, "MANIFEST.json", "SHA256SUMS.txt") if not (root / name).is_file()]
    if missing:
        raise RuntimeError(f"REIT_RESULT_REQUIRED_FILES_MISSING:{missing}")
    if not (root / "independent_verifier/verify_reit_core_model.py").is_file():
        raise RuntimeError("REIT_RESULT_VERIFIER_MISSING")
    manifest = _json(root / "MANIFEST.json")
    body = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    if hashlib.sha256(canonical).hexdigest() != manifest["manifest_sha256"]:
        raise RuntimeError("REIT_RESULT_MANIFEST_SELFHASH_MISMATCH")
    for item in manifest["files"]:
        path = root / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or _sha(path) != item["sha256"]:
            raise RuntimeError(f"REIT_RESULT_PAYLOAD_MISMATCH:{item['path']}")
    sums: dict[str, str] = {}
    for line in (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        sums[relative] = digest
    for relative, digest in sums.items():
        if not (root / relative).is_file() or _sha(root / relative) != digest:
            raise RuntimeError(f"REIT_RESULT_CHECKSUM_MISMATCH:{relative}")
    ledger = _json(root / "08_REIT_DEV6_RUN_LEDGER.json")
    attempted = tuple(item["ticker"] for item in ledger["cases"])
    if attempted != EXPECTED_DEV6[: len(attempted)]:
        raise RuntimeError("REIT_RESULT_DEV6_ORDER_MISMATCH")
    if ledger["fixed24_non_reit_live_queries"] != 0 or ledger["holdout12_queries"] != 0:
        raise RuntimeError("REIT_RESULT_FORBIDDEN_QUERY")
    holdout = _json(root / "18_HOLDOUT12_NONINTERFERENCE.json")
    if holdout["list_sha256"] != HOLDOUT_SHA or any(
        holdout[key] != 0 for key in ("queries", "discovery", "captures", "runs")
    ):
        raise RuntimeError("REIT_RESULT_HOLDOUT_INTERFERENCE")
    freeze = _json(root / "25_REIT_CORE_MODEL_FREEZE_CANDIDATE.json")
    required_true = (
        "ready_for_independent_rereview",
        "reit_core_slots_frozen_candidate",
        "reit_dev6_no_tuning",
    )
    if any(freeze[key] is not True for key in required_true):
        raise RuntimeError("REIT_RESULT_FREEZE_FLAGS_INVALID")
    if freeze["original_fixed24_verdict"] != "FAIL" or freeze["product_changed"] is not False:
        raise RuntimeError("REIT_RESULT_HISTORY_OR_PRODUCT_FLAG_INVALID")
    for name in (
        "19_FULL_RESEARCH_REGRESSION.json",
        "20_FULL_PRODUCT_REGRESSION.json",
        "21_PRIOR_ALPHA_SHARED_REGRESSION.json",
        "22_SECURITY_DEPENDENCY_REPORT.json",
        "23_BOUNDARY_GATE_V2_REPORT.json",
    ):
        if _json(root / name).get("status") != "PASS":
            raise RuntimeError(f"REIT_RESULT_GATE_NOT_PASS:{name}")
    return {
        "status": "PASS",
        "manifest_sha256": manifest["manifest_sha256"],
        "payload_count": manifest["file_count"],
        "dev6_attempted": len(attempted),
        "development_verdict": _json(root / "15_FIXED24_CORE_SLOT_V2_EVALUATION.json")["status"],
        "holdout12_queries": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    if args.artifact.is_dir():
        result = _verify(args.artifact)
    else:
        with tempfile.TemporaryDirectory(prefix="room16-reit-result-verify.") as temporary:
            root = Path(temporary)
            with zipfile.ZipFile(args.artifact) as archive:
                if any(Path(name).is_absolute() or ".." in Path(name).parts for name in archive.namelist()):
                    raise RuntimeError("REIT_RESULT_UNSAFE_ZIP_PATH")
                archive.extractall(root)
            result = _verify(root)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
