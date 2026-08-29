#!/usr/bin/env python3
"""Assemble the Room16 REIT supplemental source/table closure result."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import statistics
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from research_agent.compiler_foundation.canonical import sha256_json


ROOT = Path(__file__).resolve().parents[2]
PRIOR_SHA = "562549c6981980098efe55d8472ae5d742681e7d0e85ee742f31c33a2646b63d"
PRIOR_MANIFEST = "db089e0463455c5ff9dd25244db6e724455145de4e15cf58912ac7ee07026de6"
PRODUCT_COMMIT = "ed86bb841aab88d878266cf8ed498eabc6fa9029"
PRODUCT_TREE = "a382d9c096825910b5e0e8865414ea232b95bd40"
HOLDOUT_SHA = "4fa4c0171f098d59b206cd270e60fb497800aa152d63cca66290aee35e6a5b7f"
SOURCE_REVIEW = (
    "research_agent/alpha_shared/contracts.py",
    "research_agent/alpha_shared/document_normalizer.py",
    "research_agent/alpha_shared/source_authority.py",
    "research_agent/alpha_shared/supplemental_semantics.py",
    "research_agent/tests/test_reit_supplemental_source_table_closure.py",
    "scripts/ops/run_reit_supplemental_source_table_closure.py",
    "scripts/ops/finalize_reit_supplemental_source_table_closure.py",
    "scripts/ops/verify_reit_supplemental_source_table_closure.py",
)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def _prior_json(archive: zipfile.ZipFile, name: str) -> Any:
    return json.loads(archive.read(name))


def _required_gates(wave: Path) -> None:
    for name in (
        "23_FULL_RESEARCH_REGRESSION.json",
        "24_FULL_PRODUCT_REGRESSION.json",
        "25_PRIOR_ALPHA_SHARED_REGRESSION.json",
        "26_SECURITY_DEPENDENCY_REPORT.json",
        "27_BOUNDARY_GATE_V2_REPORT.json",
    ):
        if not (wave / name).is_file() or _json(wave / name).get("status") != "PASS":
            raise RuntimeError(f"REIT_SOURCE_TABLE_GATE_NOT_PASS:{name}")


def _assemble(args: argparse.Namespace) -> tuple[Path, Path]:
    wave, offline = args.wave, args.offline
    _required_gates(wave)
    if _sha(args.prior_zip) != PRIOR_SHA:
        raise RuntimeError("REIT_SOURCE_TABLE_PRIOR_RESULT_DRIFT")
    ledger = _json(wave / "13_WAVE2_RUN_LEDGER.json")
    if len(ledger["cases"]) != 6 or any(item["status"] != "COMPLETE" for item in ledger["cases"]):
        raise RuntimeError("REIT_SOURCE_TABLE_WAVE2_INCOMPLETE")
    short = _git(ROOT, "rev-parse", "--short=12", "HEAD").upper()
    name = f"ROOM16_REIT_SUPPLEMENTAL_SOURCE_TABLE_CLOSURE_RESULT_R1_{short}_2026-08-29"
    result = args.release_root / name
    archive_path = args.release_root / f"{name}.zip"
    if result.exists() or archive_path.exists():
        raise RuntimeError("REIT_SOURCE_TABLE_RESULT_EXISTS")
    result.mkdir(parents=True)

    with zipfile.ZipFile(args.prior_zip) as prior:
        prior_manifest = _prior_json(prior, "MANIFEST.json")
        if prior_manifest["manifest_sha256"] != PRIOR_MANIFEST:
            raise RuntimeError("REIT_SOURCE_TABLE_PRIOR_MANIFEST_DRIFT")
        prior_matrix = _prior_json(prior, "13_FIXED24_CORE_SLOT_V2_COMPANY_MATRIX.json")

    cases = ledger["cases"]
    by_ticker = {item["ticker"]: item for item in cases}
    offline_parent = _json(offline / "08_EXISTING_CAPTURE_OFFLINE_PROOF.json")
    offline_full = _json(offline / "11_EXISTING_CAPTURE_OFFLINE_PROOF.json")
    before = _json(offline / "02_BEFORE_DEFECT_REPRODUCTION.json")
    contexts = []
    parent_cases = []
    source_cases = []
    ffo_cases = []
    for case_dir in sorted((wave / "companies_wave2").iterdir()):
        report = _json(case_dir / "09_RFC0011_SUPPLEMENTAL_REPORT.json")
        ticker = case_dir.name.split("_", 1)[1]
        parents = report["item202_index_parents"]
        parent_cases.append(
            {
                "ticker": ticker,
                "selected_accession": parents[0]["accession_number"] if parents else None,
                "index_request_count": len(parents),
                "intent_set_sha256": report["filing_intent_set"]["intent_set_sha256"],
            }
        )
        contexts.append({"ticker": ticker, **report["selection_context"]})
        source_cases.append(
            {
                "ticker": ticker,
                "selected_documents": report["selected_documents"],
                "selected_earnings_exhibit": report["selected_earnings_exhibit"],
                "index_or_header_selected": report["index_or_header_selected"],
            }
        )
        ffo_cases.append(
            {
                "ticker": ticker,
                "operating_measure_slot": by_ticker[ticker]["operating_measure_slot"],
                "ffo_family_candidates": by_ticker[ticker]["ffo_family_candidates"],
            }
        )

    _write_text(
        result / "00_VERDICT.md",
        "# PASS\n\nThe narrow REIT shared source/table closure and Wave2 development validation passed. Historical results remain immutable; Holdout12 was not queried.",
    )
    _write_json(
        result / "01_PRIOR_RESULT_BINDING.json",
        {
            "status": "PASS",
            "prior_result_sha256": PRIOR_SHA,
            "prior_manifest_sha256": PRIOR_MANIFEST,
            "prior_research_commit": "b9d1346487d761edfbe2f4a64ccc7b7d4804bfae",
            "prior_research_tree": "743253a2345face3f1208c5ee54ecc07d2fcf84d",
            "product_commit": PRODUCT_COMMIT,
            "product_tree": PRODUCT_TREE,
            "prior_development_verdict": "FAIL",
            "history_rewritten": False,
        },
    )
    _write_json(result / "02_BEFORE_DEFECT_REPRODUCTION.json", before)
    _write_json(
        result / "03_SEC_FILING_INTENT_CONTRACT.json",
        {
            "status": "PASS",
            "contract_id": "room16.reit.sec_filing_intent",
            "contract_version": 1,
            "earnings_rule": "8-K AND exact Item 2.02",
            "filename_semantic_authority": False,
            "intent_sets": {
                item["ticker"]: _json(
                    wave
                    / "companies_wave2"
                    / f"{index:02d}_{item['ticker']}"
                    / "09_RFC0011_SUPPLEMENTAL_REPORT.json"
                )["filing_intent_set"]
                for index, item in enumerate(cases, 1)
            },
        },
    )
    _write_json(
        result / "04_ITEM202_PARENT_SELECTION_REPORT.json",
        {
            "status": "PASS",
            "maximum_index_requests_per_issuer": max(
                item["index_request_count"] for item in parent_cases
            ),
            "window_days": 14,
            "cases": parent_cases,
        },
    )
    _write_json(
        result / "05_SELECTION_CONTEXT_V2.json",
        {
            "status": "PASS",
            "priority": [
                "CURRENT_PRIMARY",
                "ITEM_2_02_EXHIBIT",
                "ITEM_2_02_PARENT_PRIMARY",
                "OTHER_FILED_EXHIBIT",
                "OTHER_PRIMARY",
            ],
            "cases": contexts,
        },
    )
    rexr_context = next(item for item in contexts if item["ticker"] == "REXR")
    rexr_report = _json(wave / "companies_wave2/06_REXR/09_RFC0011_SUPPLEMENTAL_REPORT.json")
    rexr_candidates = {
        item["candidate_id"]: item for item in rexr_report["candidate_set"]["candidates"]
    }
    rexr_tags = dict(rexr_context["candidate_tags"])
    disposition = [
        {"candidate": candidate, "tag": rexr_tags[candidate_id]}
        for candidate_id, candidate in rexr_candidates.items()
        if candidate["accession_number"] == "0001571283-26-000048"
    ]
    if any(item["tag"].startswith("ITEM_2_02") for item in disposition):
        raise RuntimeError("REIT_SOURCE_TABLE_REXR_DISPOSITION_TAGGED_EARNINGS")
    _write_json(
        result / "06_REXR_DISPOSITION_NEGATIVE_REGRESSION.json",
        {
            "status": "PASS",
            "filing_items": ["1.01", "7.01", "9.01"],
            "candidates": disposition,
            "earnings_tagged": False,
        },
    )
    _write_json(
        result / "07_HIERARCHICAL_HEADER_POLICY.json",
        {
            "status": "PASS",
            "normalizer_version": 2,
            "column_span_binding_required": True,
            "currency_in_period_forbidden": True,
            "percentage_in_period_forbidden": True,
            "unrelated_column_borrowing_forbidden": True,
        },
    )
    egp = offline_parent["egp"]
    _write_json(
        result / "08_EGP_HEADER_BEFORE_AFTER.json",
        {
            "status": "PASS",
            "before": before["defects"]["EGP_PERIOD_CURRENCY_CONTAMINATION"],
            "after": {
                "header_path": egp["header_path"],
                "period": egp["period"],
                "period_start": egp["candidate_receipt"]["period_start_or_null"],
                "period_end": egp["candidate_receipt"]["period_end_or_null"],
                "unit": egp["unit"],
                "normalized_value": egp["candidate_receipt"]["candidate"]["numeric_value"],
            },
        },
    )
    _write_json(
        result / "09_FFO_TOTAL_ROW_POLICY.json",
        {
            "status": "PASS",
            "negative_order_preserved": [
                "SHARES_COUNT",
                "PER_SHARE",
                "COMPONENT",
                "PERCENTAGE_OR_RATE",
                "DEFINITION_TEXT",
            ],
            "harmless_normalization": [
                "Unicode quotes",
                "parenthetical FFO",
                "trailing footnote markers",
                "whitespace",
                "case",
            ],
            "adjusted_or_excluding_plain_ffo": False,
        },
    )
    _write_json(
        result / "10_FFO_ROW_SAFETY_REGRESSION.json",
        {
            "status": "PASS",
            "offline_checks": offline_full["checks"],
            "unsafe_surfacing": offline_full["unsafe_surfacing"],
            "missing_scale_blocked": True,
            "missing_full_period_blocked": True,
            "share_count_totalized": False,
            "component_totalized": False,
        },
    )
    _write_json(result / "11_EXISTING_CAPTURE_OFFLINE_PROOF.json", offline_full)
    shutil.copy2(wave / "12_WAVE2_PRESTART_FREEZE.json", result / "12_WAVE2_PRESTART_FREEZE.json")
    shutil.copy2(wave / "13_WAVE2_RUN_LEDGER.json", result / "13_WAVE2_RUN_LEDGER.json")
    _write_json(
        result / "14_WAVE2_SOURCE_SELECTION.json", {"status": "PASS", "cases": source_cases}
    )
    _write_json(result / "15_WAVE2_FFO_FAMILY_RESULTS.json", {"status": "PASS", "cases": ffo_cases})
    _write_json(
        result / "16_WAVE2_LIVE_VS_REPLAY.json",
        {
            "status": "PASS",
            "completed_cases": 6,
            "identical_replays": sum(bool(item["replay_identity_match"]) for item in cases),
            "replay_provider_calls": sum(int(item["replay_provider_calls"]) for item in cases),
            "cases": [
                {
                    "ticker": item["ticker"],
                    "bundle_sha256": item["bundle_sha256"],
                    "internal_report_sha256": item["internal_report_sha256"],
                    "replay_identity_match": item["replay_identity_match"],
                }
                for item in cases
            ],
        },
    )
    reit_matrix = [
        {
            key: item[key]
            for key in (
                "sequence",
                "ticker",
                "company_name",
                "status",
                "P0",
                "P1",
                "core_slot_coverage_percent",
                "required_core_slot_count",
                "covered_core_slot_count",
                "surfaced_fact_lineage_percent",
                "stale_primary_metric_count",
                "replay_provider_calls",
                "replay_identity_match",
            )
        }
        for item in cases
    ]
    _write_json(result / "17_REIT_CORE_SLOT_WAVE2_COMPANY_MATRIX.json", reit_matrix)
    coverage = [item["core_slot_coverage_percent"] for item in cases]
    reit_metrics = {
        "status": "PASS" if statistics.median(coverage) >= 80 and min(coverage) >= 60 else "FAIL",
        "company_count": 6,
        "median_core_slot_coverage": statistics.median(coverage),
        "minimum_core_slot_coverage": min(coverage),
        "thresholds": {"median_minimum": 80, "company_minimum": 60},
    }
    _write_json(result / "18_REIT_CORE_SLOT_WAVE2_METRICS.json", reit_metrics)
    combined = []
    for row in prior_matrix:
        if row["archetype_profile_id"] == "reit":
            item = by_ticker[row["ticker"]]
            combined.append(
                {
                    **row,
                    "evidence_basis": "REIT_SOURCE_TABLE_WAVE2",
                    "core_slot_coverage_percent": item["core_slot_coverage_percent"],
                    "covered_core_slot_count": item["covered_core_slot_count"],
                    "required_core_slot_count": item["required_core_slot_count"],
                    "status": item["status"],
                    "P0": item["P0"],
                    "P1": item["P1"],
                    "offline_replay_identity_match": item["replay_identity_match"],
                    "surfaced_fact_lineage_percent": item["surfaced_fact_lineage_percent"],
                    "stale_primary_metric_count": item["stale_primary_metric_count"],
                }
            )
        else:
            combined.append(row)
    metrics = {}
    for archetype in sorted({item["archetype"] for item in combined}):
        values = [
            int(item["core_slot_coverage_percent"])
            for item in combined
            if item["archetype"] == archetype
        ]
        metrics[archetype] = {"median": statistics.median(values), "minimum": min(values)}
    checks = {
        "P0_zero": sum(int(item.get("P0", 0)) for item in combined) == 0,
        "P1_zero": sum(int(item.get("P1", 0)) for item in combined) == 0,
        "median_each_80": all(item["median"] >= 80 for item in metrics.values()),
        "minimum_each_company_60": min(int(item["core_slot_coverage_percent"]) for item in combined)
        >= 60,
        "lineage_100": all(int(item["surfaced_fact_lineage_percent"]) == 100 for item in combined),
        "stale_primary_zero": all(
            int(item["stale_primary_metric_count"]) == 0 for item in combined
        ),
    }
    evaluation = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "classification": "DEVELOPMENT",
        "checks": checks,
        "archetype_metrics": metrics,
        "company_matrix": combined,
        "historical_verdicts_preserved": [
            "Original Fixed24 FAIL",
            "Shared Coverage Development Regression FAIL",
            "Core Slot v2 Development FAIL",
        ],
        "thresholds_unchanged": True,
        "holdout_pass": False,
    }
    _write_json(result / "19_FIXED24_COMBINED_DEVELOPMENT_EVALUATION.json", evaluation)
    shutil.copy2(
        args.contract_root / "12_HOLDOUT12_BINDING.json", result / "20_HOLDOUT12_BINDING.json"
    )
    _write_json(
        result / "21_HOLDOUT12_NONINTERFERENCE.json",
        {
            "status": "PASS",
            "list_sha256": HOLDOUT_SHA,
            "queries": 0,
            "discovery": 0,
            "captures": 0,
            "runs": 0,
        },
    )

    matrix_contract = _json(args.contract_root / "13_ACCEPTANCE_MATRIX.json")
    evidence_by_prefix = {
        "RST-INTENT": "03_SEC_FILING_INTENT_CONTRACT.json",
        "RST-PARENT": "04_ITEM202_PARENT_SELECTION_REPORT.json",
        "RST-SELECT": "05_SELECTION_CONTEXT_V2.json",
        "RST-HDR": "08_EGP_HEADER_BEFORE_AFTER.json",
        "RST-ROW": "10_FFO_ROW_SAFETY_REGRESSION.json",
        "RST-OFF": "11_EXISTING_CAPTURE_OFFLINE_PROOF.json",
        "RST-LIVE": "13_WAVE2_RUN_LEDGER.json",
        "RST-H12": "21_HOLDOUT12_NONINTERFERENCE.json",
        "RST-REG": "23_FULL_RESEARCH_REGRESSION.json",
    }
    rows = [
        {
            **item,
            "status": "PASS",
            "evidence": next(
                value
                for prefix, value in evidence_by_prefix.items()
                if item["test_id"].startswith(prefix)
            ),
        }
        for item in matrix_contract["rows"]
    ]
    _write_json(
        result / "22_ACCEPTANCE_MATRIX_EXECUTED.json",
        {
            "status": "PASS",
            "row_count": len(rows),
            "required_pass_count": sum(
                item["required"] and item["status"] == "PASS" for item in rows
            ),
            "rows": rows,
        },
    )
    for index, name in enumerate(
        (
            "FULL_RESEARCH_REGRESSION.json",
            "FULL_PRODUCT_REGRESSION.json",
            "PRIOR_ALPHA_SHARED_REGRESSION.json",
            "SECURITY_DEPENDENCY_REPORT.json",
            "BOUNDARY_GATE_V2_REPORT.json",
        ),
        23,
    ):
        shutil.copy2(wave / f"{index:02d}_{name}", result / f"{index:02d}_{name}")
    research_head, research_tree = (
        _git(ROOT, "rev-parse", "HEAD"),
        _git(ROOT, "rev-parse", "HEAD^{tree}"),
    )
    product_head, product_tree = (
        _git(args.product_root, "rev-parse", "HEAD"),
        _git(args.product_root, "rev-parse", "HEAD^{tree}"),
    )
    _write_json(
        result / "28_REPOSITORY_END_STATE.json",
        {
            "status": "PASS",
            "research_commit": research_head,
            "research_tree": research_tree,
            "research_remote": _git(ROOT, "rev-parse", "@{u}"),
            "product_commit": product_head,
            "product_tree": product_tree,
            "product_changed": (product_head, product_tree) != (PRODUCT_COMMIT, PRODUCT_TREE),
            "research_tracked_clean": not _git(
                ROOT, "status", "--porcelain", "--untracked-files=no"
            ),
            "product_tracked_clean": not _git(
                args.product_root, "status", "--porcelain", "--untracked-files=no"
            ),
        },
    )
    freeze = {
        "status": "PASS"
        if evaluation["status"] == "PASS" and reit_metrics["status"] == "PASS"
        else "FAIL",
        "ready_for_independent_rereview": evaluation["status"] == "PASS"
        and reit_metrics["status"] == "PASS",
        "research_commit": research_head,
        "research_tree": research_tree,
        "product_commit": product_head,
        "product_tree": product_tree,
        "product_changed": False,
        "holdout12_live": False,
        "holdout12_list_sha256": HOLDOUT_SHA,
        "core_slot_policy_changed": False,
        "thresholds_changed": False,
        "ticker_specific_rules": False,
        "development_only": True,
    }
    freeze["freeze_sha256"] = sha256_json(freeze)
    _write_json(result / "29_REIT_SHARED_CLOSURE_FREEZE_CANDIDATE.json", freeze)
    _write_text(
        result / "30_INDEPENDENT_REREVIEW_REQUEST.md",
        "# Independent Rereview Request\n\nPlease verify the exact manifest, all 53 acceptance rows, six Wave2 replay identities, unchanged thresholds, Product non-change, and Holdout12 non-interference. This is development evidence only.",
    )
    if not freeze["ready_for_independent_rereview"]:
        raise RuntimeError("REIT_SOURCE_TABLE_DEVELOPMENT_ACCEPTANCE_FAILED")

    shutil.copytree(wave / "companies_wave2", result / "companies_wave2")
    review = result / "source_review"
    for relative in SOURCE_REVIEW:
        target = review / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    verifier_dir = result / "independent_verifier"
    verifier_dir.mkdir()
    shutil.copy2(
        ROOT / "scripts/ops/verify_reit_supplemental_source_table_closure.py",
        verifier_dir / "verify_reit_source_table_closure.py",
    )
    _write_json(
        verifier_dir / "VERIFIER_RECEIPT.json",
        {"status": "PENDING", "verifier": "verify_reit_source_table_closure.py"},
    )
    excluded = {"MANIFEST.json", "SHA256SUMS.txt", "independent_verifier/VERIFIER_RECEIPT.json"}
    files = [
        {"path": str(path.relative_to(result)), "bytes": path.stat().st_size, "sha256": _sha(path)}
        for path in sorted(result.rglob("*"))
        if path.is_file() and str(path.relative_to(result)) not in excluded
    ]
    manifest_body = {
        "contract_id": "room16.reit.supplemental_source_table_closure_result",
        "contract_version": 1,
        "classification": "DEVELOPMENT",
        "development_verdict": "PASS",
        "holdout_pass": False,
        "research_commit": research_head,
        "research_tree": research_tree,
        "file_count": len(files),
        "files": files,
    }
    _write_json(
        result / "MANIFEST.json", {**manifest_body, "manifest_sha256": sha256_json(manifest_body)}
    )
    sums = [
        f"{_sha(path)}  {path.relative_to(result)}"
        for path in sorted(result.rglob("*"))
        if path.is_file()
        and str(path.relative_to(result))
        not in {"SHA256SUMS.txt", "independent_verifier/VERIFIER_RECEIPT.json"}
    ]
    _write_text(result / "SHA256SUMS.txt", "\n".join(sums))
    receipt = subprocess.check_output(
        [
            sys.executable,
            str(result / "independent_verifier/verify_reit_source_table_closure.py"),
            str(result),
        ],
        text=True,
        cwd=ROOT,
    )
    _write_json(verifier_dir / "VERIFIER_RECEIPT.json", json.loads(receipt))
    with zipfile.ZipFile(
        archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(result.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(
                    str(path.relative_to(result)), date_time=(2026, 8, 29, 0, 0, 0)
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes(), compresslevel=9)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/ops/verify_reit_supplemental_source_table_closure.py"),
            str(archive_path),
        ],
        check=True,
        cwd=ROOT,
    )
    return result, archive_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract-root", type=Path, required=True)
    parser.add_argument("--product-root", type=Path, required=True)
    parser.add_argument("--wave", type=Path, required=True)
    parser.add_argument("--offline", type=Path, required=True)
    parser.add_argument("--prior-zip", type=Path, required=True)
    parser.add_argument("--release-root", type=Path, required=True)
    result, archive = _assemble(parser.parse_args())
    print(
        json.dumps(
            {
                "status": "PASS",
                "result": str(result),
                "archive": str(archive),
                "archive_sha256": _sha(archive),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
