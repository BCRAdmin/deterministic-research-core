#!/usr/bin/env python3
"""Stdlib-only verifier for Room16 Holdout12 result ZIPs."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


EXCLUDED = {"MANIFEST.json", "SHA256SUMS.txt", "independent_verifier/VERIFIER_RECEIPT.json"}
TICKERS = ("SNOW", "DDOG", "ZS", "VICI", "WELL", "SPG", "TFC", "BK", "STT", "VLO", "PSX", "DVN")
ARCHETYPES = ("Software/SaaS", "REIT", "Bank", "Integrated Energy")
PLAN_SHA = "4fa4c0171f098d59b206cd270e60fb497800aa152d63cca66290aee35e6a5b7f"
COMPANIES_SHA = "dff991277f1c93e4857f9bb267b8bca80b9e6b3d0d8de2ab1561a61a3f0efadf"
THRESHOLDS_SHA = "68e7c44ecb40114a89c8441229b3a1c4a31b6b0e05cb9e8135f901a73b505fd7"
PRODUCT_COMMIT = "ed86bb841aab88d878266cf8ed498eabc6fa9029"
PRODUCT_TREE = "a382d9c096825910b5e0e8865414ea232b95bd40"


def canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def selfhash(value: dict[str, Any], field: str) -> bool:
    body = dict(value)
    observed = body.pop(field, None)
    return observed == digest(canonical(body))


def _load(archive: zipfile.ZipFile, path: str) -> Any:
    return json.loads(archive.read(path))


def verify_zip(path: Path, full_zip: Path | None = None) -> dict[str, Any]:
    failures: list[str] = []
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or archive.testzip():
            failures.append("zip_integrity")
        for name in names:
            item = PurePosixPath(name)
            if item.is_absolute() or ".." in item.parts:
                failures.append(f"unsafe_path:{name}")
        manifest = _load(archive, "MANIFEST.json")
        if not selfhash(manifest, "manifest_sha256"):
            failures.append("manifest_selfhash")
        listed = {row["path"]: row for row in manifest.get("files", [])}
        expected = set(names) - EXCLUDED
        if set(listed) != expected:
            failures.append("manifest_closure")
        for name, row in listed.items():
            payload = archive.read(name)
            if len(payload) != row.get("bytes") or digest(payload) != row.get("sha256"):
                failures.append(f"payload:{name}")
        freeze = _load(archive, "03_FINAL_SHARED_COVERAGE_FREEZE.json")
        envelope = _load(archive, "05_HOLDOUT12_EXECUTION_ENVELOPE.json")
        authority = _load(archive, "06_COMPAT_EXECUTION_AUTHORITY.json")
        receipts = _load(archive, "07_HOLDOUT12_ALL_PREFLIGHTS.json")
        prestart = _load(archive, "08_HOLDOUT12_PRESTART_STATE.json")
        evaluation = _load(archive, "14_HOLDOUT12_THRESHOLD_EVALUATION.json")
        if not selfhash(freeze, "freeze_sha256"):
            failures.append("freeze_selfhash")
        if not selfhash(envelope, "envelope_sha256"):
            failures.append("envelope_selfhash")
        if not selfhash(authority, "authority_sha256"):
            failures.append("authority_selfhash")
        if freeze.get("holdout12_plan_sha256") != PLAN_SHA or envelope.get("holdout_plan_sha256") != PLAN_SHA:
            failures.append("plan_binding")
        if freeze.get("holdout12_companies_sha256") != COMPANIES_SHA or envelope.get("companies_sha256") != COMPANIES_SHA:
            failures.append("companies_binding")
        if freeze.get("holdout12_thresholds_sha256") != THRESHOLDS_SHA or envelope.get("thresholds_sha256") != THRESHOLDS_SHA:
            failures.append("threshold_binding")
        if (freeze.get("product_commit"), freeze.get("product_tree")) != (PRODUCT_COMMIT, PRODUCT_TREE):
            failures.append("product_binding")
        if manifest.get("research_commit") != freeze.get("final_research_commit") or manifest.get("research_tree") != freeze.get("final_research_tree"):
            failures.append("research_binding")
        if envelope.get("final_shared_freeze_sha256") != freeze.get("freeze_sha256") or envelope.get("compat_execution_authority_sha256") != authority.get("authority_sha256"):
            failures.append("envelope_binding")
        cases = authority.get("ordered_cases", [])
        if len(cases) != 12 or [row.get("ticker") for row in cases] != list(TICKERS):
            failures.append("exact_order")
        if len(receipts) != 12 or prestart.get("preflight_count") != 12 or prestart.get("provider_calls") != 0:
            failures.append("prestart")
        for index, (case, receipt) in enumerate(zip(cases, receipts), 1):
            if receipt.get("sequence") != index or receipt.get("ticker") != case.get("ticker") or receipt.get("authority_sha256") != authority.get("authority_sha256") or not selfhash(receipt, "receipt_sha256"):
                failures.append(f"receipt:{index}")
        completed: list[dict[str, Any]] = []
        for index, ticker in enumerate(TICKERS, 1):
            prefix = f"companies/{index:02d}_{ticker}/"
            verdict_name = prefix + "00_CASE_VERDICT.json"
            if verdict_name not in names:
                continue
            verdict = _load(archive, verdict_name)
            if verdict.get("status") != "COMPLETE":
                continue
            completed.append(verdict)
            for number in range(1, 22):
                if not any(name.startswith(prefix + f"{number:02d}_") for name in names):
                    failures.append(f"case_evidence:{ticker}:{number:02d}")
            receipt = _load(archive, prefix + "01_AUTHORIZATION_RECEIPT.json")
            ledger = _load(archive, prefix + "18_H4_FULL_CASE_LEDGER.json")
            replay = _load(archive, prefix + "19_OFFLINE_REPLAY_REPORT.json")
            if not ledger.get("authorization_precedes_provider") or ledger.get("events", [{}])[0].get("input_sha256s", [None])[0] != receipt.get("receipt_sha256"):
                failures.append(f"origin:{ticker}")
            if replay.get("network_provider_calls") != 0 or not verdict.get("replay_identity_match"):
                failures.append(f"replay:{ticker}")
        metrics = _load(archive, "13_HOLDOUT12_METRICS.json")
        expected_checks = {
            "P0_zero": metrics.get("P0") == 0,
            "P1_zero": metrics.get("P1") == 0,
            "ticker_specific_patches_zero": metrics.get("ticker_specific_semantic_patches") == 0,
            "stale_primary_zero": metrics.get("stale_primary") == 0,
            "lineage_100": metrics.get("surfaced_lineage_percent") == 100,
            "complete_reports_11": metrics.get("complete_canonical_reports", 0) >= 11,
            "each_archetype_2": all(metrics.get("complete_by_archetype", {}).get(name, 0) >= 2 for name in ARCHETYPES),
            "replay_identity_100": metrics.get("offline_replay_identity_percent") == 100,
            "manual_intervention_max_1": metrics.get("manual_semantic_intervention_count", 0) <= 1,
            "median_coverage_each_80": all(metrics.get("median_core_slot_coverage_each", {}).get(name, 0) >= 80 for name in ARCHETYPES),
            "minimum_coverage_60": metrics.get("minimum_company_core_slot_coverage", 0) >= 60,
            "required_sections_90": metrics.get("minimum_required_section_completeness", 0) >= 90,
            "replay_provider_calls_zero": metrics.get("replay_provider_calls") == 0,
        }
        if evaluation.get("checks") != expected_checks or evaluation.get("status") != ("PASS" if all(expected_checks.values()) else "FAIL"):
            failures.append("threshold_arithmetic")
        verdict_text = archive.read("00_FINALIZE_AND_HOLDOUT_VERDICT.md").decode()
        expected_verdict = "HOLDOUT12_STOPPED_P0" if metrics.get("P0") else "HOLDOUT12_STOPPED_P1" if metrics.get("P1") else "HOLDOUT12_PASS" if evaluation.get("status") == "PASS" else "HOLDOUT12_FAIL"
        if expected_verdict not in verdict_text:
            failures.append("verdict_consistency")
        compact = bool(manifest.get("compact"))
        if compact:
            receipt = _load(archive, "COMPACT_TRANSPORT_RECEIPT.json")
            binding = manifest.get("full_binding") or {}
            if receipt.get("full_zip_sha256") != binding.get("full_zip_sha256") or receipt.get("full_zip_bytes") != binding.get("full_zip_bytes") or receipt.get("full_manifest_sha256") != binding.get("full_manifest_sha256"):
                failures.append("compact_binding")
            if full_zip is not None:
                if digest(full_zip.read_bytes()) != receipt.get("full_zip_sha256") or full_zip.stat().st_size != receipt.get("full_zip_bytes"):
                    failures.append("compact_full_zip_identity")
    return {"status": "PASS" if not failures else "FAIL", "failures": failures, "manifest_sha256": manifest.get("manifest_sha256"), "payload_count": len(listed), "completed_cases": len(completed), "threshold_status": evaluation.get("status"), "compact": compact}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    parser.add_argument("--full-zip", type=Path)
    args = parser.parse_args()
    result = verify_zip(args.target, args.full_zip)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
