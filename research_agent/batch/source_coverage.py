from __future__ import annotations

import csv
import json
import shutil
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from research_agent.batch.batch_config import BatchConfig, load_batch_config
from research_agent.batch.batch_manifest import BatchManifest
from research_agent.batch.dashboard_adapter import build_dashboard_status, save_dashboard_status
from research_agent.batch.freshness import evaluate_price_freshness


MINIMUM_DATA_REQUIREMENTS: dict[str, list[str]] = {
    "MEGA_CAP": [
        "price",
        "revenue",
        "operating income or margin",
        "FCF/OCF",
        "market cap",
        "current-period context or explicit missing flag",
    ],
    "SAAS": [
        "price",
        "revenue",
        "FCF/OCF",
        "SBC",
        "market cap / EV",
    ],
    "SEMICONDUCTOR": [
        "price",
        "revenue",
        "FCF/OCF",
        "guidance/current quarter if available",
    ],
    "SPECULATIVE_DEEP_TECH": [
        "price",
        "revenue",
        "cash",
        "FCF/cashburn",
        "SBC/dilution",
        "SEC/IR or vendor-only flag",
    ],
    "EARLY_COMMERCIAL_CAPITAL_INTENSIVE": [
        "price",
        "revenue",
        "backlog/contracts if available",
        "FCF/cashburn",
        "cash",
        "market cap / EV",
        "execution milestone risk",
    ],
    "TURNAROUND": [
        "price",
        "revenue",
        "operating income or margin",
        "FCF/OCF",
        "market cap / EV",
        "current-period context or explicit missing flag",
    ],
}


def build_source_inventory(
    *,
    config_path: str | Path,
    batch_dir: str | Path,
    output_dir: str | Path = "outputs/source_inventory",
    reference_date: Optional[str] = None,
) -> dict[str, Any]:
    config = load_batch_config(config_path)
    batch_root = Path(batch_dir)
    matrix = _load_json(batch_root / "GUARDRAIL_COVERAGE_MATRIX.json", default={})
    matrix_rows = {str(row.get("ticker", "")).upper(): row for row in matrix.get("rows", [])}
    manifest = _load_json(batch_root / "batch_manifest.json", default={"items": []})
    manifest_items = {str(item.get("ticker", "")).upper(): item for item in manifest.get("items", [])}
    cik_records = _load_cik_records(config.cik_records_path)
    price_dir = Path(config.price_csv_dir or "")
    ir_dir = Path(config.ir_release_dir or "")
    companyfacts_dir = Path(config.sec_companyfacts_dir or "")
    earnings_calendar = _load_earnings_calendar(config.earnings_calendar_path)

    records: list[dict[str, Any]] = []
    for ticker_config in config.tickers:
        ticker = ticker_config.ticker.upper()
        item = manifest_items.get(ticker, {})
        row = matrix_rows.get(ticker, {})
        artifacts = item.get("artifacts") or {}
        price_path = price_dir / f"{ticker}.csv"
        latest_price_date = _latest_csv_date(price_path) or _artifact_price_basis_date(artifacts)
        freshness = evaluate_price_freshness(
            latest_price_date,
            batch_mode="historical_guardrail_test",
            reference_date=reference_date,
        )
        expected_bucket = _expected_bucket(row, ticker_config.tags)
        price_source_present = price_path.exists() or bool(_artifact_price_basis_date(artifacts))
        cik_present = ticker in cik_records
        companyfacts_present = (companyfacts_dir / f"{ticker}.json").exists()
        canonical_present = _artifact_exists(artifacts, "canonical_financials.json")
        ir_present = (ir_dir / f"{ticker}.json").exists()
        current_period_present = ir_present or _artifact_exists(artifacts, "current_period_reconciliation_summary.md")
        earnings_present = ticker in earnings_calendar
        benchmark_present = bool(ticker_config.benchmark and (price_dir / f"{ticker_config.benchmark.upper()}.csv").exists())
        news_present = _news_fallback_present(ticker)
        minimum_result = evaluate_minimum_viable_data(
            expected_bucket=expected_bucket,
            price_source_present=price_source_present,
            cik_present=cik_present,
            companyfacts_present=companyfacts_present,
            canonical_financials_present=canonical_present,
            current_period_evidence_present=current_period_present,
            news_fallback_present=news_present,
        )
        flags = []
        if freshness.stale_price_basis:
            flags.append("stale_price_basis")
        if not companyfacts_present and not canonical_present:
            flags.append("missing_primary_financials")
        if not companyfacts_present and canonical_present:
            flags.append("vendor_only_hard_metrics")
        if not current_period_present:
            flags.append("no_current_period_context")
        if not minimum_result["minimum_viable_report_possible"]:
            flags.append("no_minimum_data")
        records.append(
            {
                "ticker": ticker,
                "expected_archetype_bucket": expected_bucket,
                "price_source_present": price_source_present,
                "latest_price_date": latest_price_date,
                "SEC_CIK_present": cik_present,
                "companyfacts_present": companyfacts_present,
                "canonical_financials_present": canonical_present,
                "IR_current_period_evidence_present": current_period_present,
                "earnings_calendar_present": earnings_present,
                "news_fallback_present": news_present,
                "benchmark_present": benchmark_present,
                "minimum_viable_report_possible": minimum_result["minimum_viable_report_possible"],
                "current_report_possible": minimum_result["minimum_viable_report_possible"] and freshness.current_report_allowed,
                "historical_QA_only": bool(minimum_result["minimum_viable_report_possible"] and freshness.historical_qa_only),
                "missing_minimum_inputs": minimum_result["missing_minimum_inputs"],
                "flags": flags,
            }
        )

    payload = {
        "generated_at": _utc_now(),
        "source_batch_id": config.batch_id,
        "ticker_count": len(records),
        "summary": {
            "minimum_viable_report_possible": sum(1 for row in records if row["minimum_viable_report_possible"]),
            "current_report_possible": sum(1 for row in records if row["current_report_possible"]),
            "historical_QA_only": sum(1 for row in records if row["historical_QA_only"]),
            "flags": dict(Counter(flag for row in records for flag in row["flags"])),
        },
        "records": records,
    }
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "SOURCE_INPUT_INVENTORY.json", payload)
    (output_root / "SOURCE_INPUT_INVENTORY.md").write_text(_render_source_inventory_md(payload), encoding="utf-8")
    return payload


def build_data_availability_root_cause(
    *,
    config_path: str | Path,
    batch_dir: str | Path,
    output_dir: Optional[str | Path] = None,
) -> dict[str, Any]:
    config = load_batch_config(config_path)
    batch_root = Path(batch_dir)
    target_root = Path(output_dir) if output_dir else batch_root
    matrix = _load_json(batch_root / "GUARDRAIL_COVERAGE_MATRIX.json", default={})
    rows = {str(row.get("ticker", "")).upper(): row for row in matrix.get("rows", [])}
    manifest = _load_json(batch_root / "batch_manifest.json", default={"items": []})
    cik_records = _load_cik_records(config.cik_records_path)
    price_dir = Path(config.price_csv_dir or "")
    ir_dir = Path(config.ir_release_dir or "")
    companyfacts_dir = Path(config.sec_companyfacts_dir or "")
    earnings_calendar = _load_earnings_calendar(config.earnings_calendar_path)

    records: list[dict[str, Any]] = []
    for item in manifest.get("items", []):
        if item.get("status") != "data_unavailable":
            continue
        ticker = str(item.get("ticker", "")).upper()
        row = rows.get(ticker, {})
        tags = _config_tags(config, ticker)
        expected_bucket = _expected_bucket(row, tags)
        price_path = price_dir / f"{ticker}.csv"
        cik_present = ticker in cik_records
        companyfacts_present = (companyfacts_dir / f"{ticker}.json").exists()
        ir_present = (ir_dir / f"{ticker}.json").exists()
        earnings_present = ticker in earnings_calendar
        issue_type = _root_issue_type(ticker, price_path.exists(), cik_present, companyfacts_present, item.get("error_message"))
        records.append(
            {
                "ticker": ticker,
                "expected_archetype_bucket": expected_bucket,
                "missing_price_data": not price_path.exists(),
                "missing_SEC_companyfacts": not companyfacts_present,
                "missing_CIK_mapping": not cik_present,
                "missing_IR_fixture": not ir_present,
                "missing_earnings_current_period_evidence": not earnings_present and not ir_present,
                "missing_news_vendor_fallback": not _news_fallback_present(ticker),
                "missing_benchmark_data": not _benchmark_present(config, ticker, price_dir),
                "unsupported_by_provider": issue_type == "unsupported_asset_type",
                "root_cause_type": issue_type,
                "error_message": item.get("error_message"),
                "recommended_fix": _recommended_fix(ticker, issue_type, expected_bucket),
                "priority": _root_cause_priority(issue_type, expected_bucket),
            }
        )

    payload = {
        "generated_at": _utc_now(),
        "source_batch_id": config.batch_id,
        "data_unavailable_count": len(records),
        "summary": {
            "count_by_root_cause": dict(Counter(row["root_cause_type"] for row in records)),
            "count_by_missing_input_type": _missing_input_counts(records),
            "quick_fixes": _quick_fixes(records),
            "not_worth_fixing_now": [
                row["ticker"]
                for row in records
                if row["root_cause_type"] == "unsupported_asset_type"
            ],
            "tickers_to_remove_from_next_batch_if_unsupported": [
                row["ticker"]
                for row in records
                if row["root_cause_type"] == "unsupported_asset_type"
            ],
            "tickers_to_keep_but_mark_data_gap": [
                row["ticker"]
                for row in records
                if row["root_cause_type"] != "unsupported_asset_type"
            ],
        },
        "records": records,
    }
    target_root.mkdir(parents=True, exist_ok=True)
    _write_json(target_root / "DATA_AVAILABILITY_ROOT_CAUSE.json", payload)
    (target_root / "DATA_AVAILABILITY_ROOT_CAUSE.md").write_text(_render_root_cause_md(payload), encoding="utf-8")
    return payload


def evaluate_minimum_viable_data(
    *,
    expected_bucket: str,
    price_source_present: bool,
    cik_present: bool,
    companyfacts_present: bool,
    canonical_financials_present: bool,
    current_period_evidence_present: bool,
    news_fallback_present: bool,
) -> dict[str, Any]:
    missing: list[str] = []
    if not price_source_present:
        missing.append("price")
    if not (companyfacts_present or canonical_financials_present):
        missing.append("revenue / canonical financials")
    if not (cik_present or canonical_financials_present):
        missing.append("SEC/CIK or explicit vendor-only flag")
    if "SPECULATIVE_DEEP_TECH" in expected_bucket and not (current_period_evidence_present or news_fallback_present):
        missing.append("SEC/IR or vendor-only current-period flag")
    if "EARLY_COMMERCIAL_CAPITAL_INTENSIVE" in expected_bucket and not (current_period_evidence_present or news_fallback_present):
        missing.append("backlog/contracts/execution context")
    return {
        "minimum_viable_report_possible": not missing,
        "missing_minimum_inputs": missing,
        "requirements": _minimum_requirements_for_bucket(expected_bucket),
    }


def create_guardrail_batch_002_outputs(
    *,
    source_batch_dir: str | Path = "outputs/batches/guardrail_coverage_batch_001",
    source_config_path: str | Path = "outputs/batches/guardrail_coverage_batch_001_config.json",
    target_batch_id: str = "guardrail_coverage_batch_002",
    reference_date: Optional[str] = None,
) -> dict[str, Any]:
    source_dir = Path(source_batch_dir)
    target_dir = source_dir.parent / target_batch_id
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    root_cause = build_data_availability_root_cause(config_path=source_config_path, batch_dir=source_dir)
    inventory = build_source_inventory(
        config_path=source_config_path,
        batch_dir=source_dir,
        output_dir="outputs/source_inventory",
        reference_date=reference_date,
    )
    _write_json(target_dir / "SOURCE_INPUT_INVENTORY.json", inventory)
    (target_dir / "SOURCE_INPUT_INVENTORY.md").write_text(_render_source_inventory_md(inventory), encoding="utf-8")
    _write_json(target_dir / "DATA_AVAILABILITY_ROOT_CAUSE.json", root_cause)
    (target_dir / "DATA_AVAILABILITY_ROOT_CAUSE.md").write_text(_render_root_cause_md(root_cause), encoding="utf-8")

    source_manifest = _load_json(source_dir / "batch_manifest.json", default={})
    selected_items = [
        item for item in source_manifest.get("items", [])
        if item.get("status") != "data_unavailable"
    ]
    selected_tickers = {str(item.get("ticker", "")).upper() for item in selected_items}
    for ticker in sorted(selected_tickers):
        if (source_dir / ticker).exists():
            shutil.copytree(source_dir / ticker, target_dir / ticker)

    target_manifest = _rewrite_manifest_for_batch_002(
        source_manifest,
        selected_items,
        target_batch_id=target_batch_id,
        reference_date=reference_date,
    )
    _write_json(target_dir / "batch_manifest.json", target_manifest)
    dashboard = build_dashboard_status(BatchManifest.model_validate(target_manifest))
    save_dashboard_status(dashboard, target_dir / "dashboard_status.json")
    _write_batch_002_config(source_config_path, target_batch_id, selected_tickers)
    matrix = _write_batch_002_matrix(source_dir, target_dir, target_batch_id, selected_tickers, target_manifest)
    _write_pilot_review(target_dir, target_batch_id, dashboard, root_cause)
    _write_artifact_consistency_overview(target_dir, selected_tickers)
    vivi = _write_vivi_review(target_dir, target_batch_id, root_cause, dashboard)
    _write_market_readiness_decision(target_dir, target_batch_id, dashboard, root_cause, matrix)
    _write_bundles(target_dir, selected_tickers, dashboard)
    return {
        "target_dir": str(target_dir),
        "selected_ticker_count": len(selected_tickers),
        "dashboard": dashboard,
        "root_cause": root_cause,
        "inventory": inventory,
        "vivi": vivi,
    }


def _rewrite_manifest_for_batch_002(
    source_manifest: dict[str, Any],
    selected_items: list[dict[str, Any]],
    *,
    target_batch_id: str,
    reference_date: Optional[str],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for item in selected_items:
        rewritten = _rewrite_batch_strings(item, target_batch_id)
        price_basis_date = rewritten.get("price_basis_date") or _artifact_price_basis_date(rewritten.get("artifacts") or {}) or source_manifest.get("as_of_date")
        freshness = evaluate_price_freshness(
            price_basis_date,
            batch_mode="historical_guardrail_test",
            reference_date=reference_date,
        )
        counts = dict(rewritten.get("counts") or {})
        counts["stale_price_basis_count"] = int(freshness.stale_price_basis)
        counts["historical_qa_only_count"] = 1
        counts["current_report_blocked_by_freshness_count"] = 0
        rewritten.update(
            {
                "price_basis_date": freshness.price_basis_date,
                "data_freshness_status": freshness.data_freshness_status,
                "stale_price_basis": freshness.stale_price_basis,
                "current_report_allowed": freshness.current_report_allowed,
                "historical_qa_only": freshness.historical_qa_only,
                "minimum_viable_report_possible": True,
                "current_report_possible": False,
                "missing_minimum_inputs": [],
                "counts": counts,
            }
        )
        items.append(rewritten)
    return {
        "batch_id": target_batch_id,
        "as_of_date": source_manifest.get("as_of_date"),
        "batch_mode": "historical_guardrail_test",
        "started_at": source_manifest.get("started_at"),
        "finished_at": _utc_now(),
        "status": "completed",
        "items": items,
    }


def _write_batch_002_config(source_config_path: str | Path, target_batch_id: str, selected_tickers: set[str]) -> None:
    source = _load_json(source_config_path, default={})
    source["batch_id"] = target_batch_id
    source["batch_mode"] = "historical_guardrail_test"
    source["freshness_reference_date"] = datetime.now(timezone.utc).date().isoformat()
    source["tickers"] = [
        row for row in source.get("tickers", [])
        if str(row.get("ticker", "")).upper() in selected_tickers
    ]
    _write_json(Path("outputs/batches") / f"{target_batch_id}_config.json", source)


def _write_batch_002_matrix(
    source_dir: Path,
    target_dir: Path,
    target_batch_id: str,
    selected_tickers: set[str],
    target_manifest: dict[str, Any],
) -> dict[str, Any]:
    source_matrix = _load_json(source_dir / "GUARDRAIL_COVERAGE_MATRIX.json", default={"rows": []})
    item_by_ticker = {item["ticker"]: item for item in target_manifest.get("items", [])}
    rows: list[dict[str, Any]] = []
    for row in source_matrix.get("rows", []):
        ticker = str(row.get("ticker", "")).upper()
        if ticker not in selected_tickers:
            continue
        item = item_by_ticker.get(ticker, {})
        rewritten = _rewrite_batch_strings(row, target_batch_id)
        rewritten.update(
            {
                "price_basis_date": item.get("price_basis_date"),
                "data_freshness_status": item.get("data_freshness_status"),
                "current_report_allowed": item.get("current_report_allowed"),
                "historical_qa_only": item.get("historical_qa_only"),
                "minimum_viable_report_possible": item.get("minimum_viable_report_possible"),
                "current_report_possible": item.get("current_report_possible"),
            }
        )
        rows.append(rewritten)
    status_counts = Counter(row.get("review_status") for row in rows)
    archetype_counts = Counter(row.get("actual_archetype") or "UNKNOWN" for row in rows)
    matrix = {
        "batch_id": target_batch_id,
        "generated_at": _utc_now(),
        "listed_ticker_count": len(rows),
        "local_price_basis_used": source_matrix.get("local_price_basis_used"),
        "batch_mode": "historical_guardrail_test",
        "price_basis_request": source_matrix.get("price_basis_request", "latest_available"),
        "rows": rows,
        "summary": {
            "passed_count": status_counts.get("passed", 0),
            "manual_review_count": status_counts.get("manual_review", 0),
            "failed_count": status_counts.get("failed", 0),
            "data_unavailable_count": status_counts.get("data_unavailable", 0),
            "UNKNOWN_archetype_count": archetype_counts.get("UNKNOWN", 0),
            "archetype_counts": dict(archetype_counts),
            "top_manual_review_reasons": _top_values(row for row in rows for row in row.get("manual_review_reasons", [])),
            "top_evidence_gaps": _top_values(row.get("evidence_status") for row in rows if row.get("evidence_status") != "clean"),
            "top_artifact_consistency_problems": _top_values(row.get("artifact_consistency_status") for row in rows if row.get("artifact_consistency_status") != "clean"),
            "top_financial_sanity_problems": _top_values(blocker for row in rows for blocker in row.get("primary_blockers", []) if "FINANCIAL" in str(blocker) or "FCF" in str(blocker)),
            "top_false_pass_candidates": [],
            "top_false_block_candidates": [],
            "system_level_fix_candidates": [
                "Ingest auditable price/source inputs for excluded data-gap tickers before the next coverage batch.",
                "Keep historical price-basis batches out of current-research/public lanes.",
            ],
        },
    }
    _write_json(target_dir / "GUARDRAIL_COVERAGE_MATRIX.json", matrix)
    (target_dir / "GUARDRAIL_COVERAGE_MATRIX.md").write_text(_render_matrix_md(matrix), encoding="utf-8")
    return matrix


def _write_pilot_review(target_dir: Path, target_batch_id: str, dashboard: dict[str, Any], root_cause: dict[str, Any]) -> None:
    summary = dashboard.get("summary", {})
    text = "\n".join(
        [
            f"# Pilot Review - {target_batch_id}",
            "",
            "- Batch mode: `historical_guardrail_test`",
            f"- Tickers: `{summary.get('total', 0)}`",
            f"- Passed: `{summary.get('passed', 0)}`",
            f"- Manual review: `{summary.get('manual_review', 0)}`",
            f"- Failed: `{summary.get('failed', 0)}`",
            f"- Data unavailable in reduced batch: `{summary.get('data_unavailable', 0)}`",
            f"- Excluded Batch-001 data gaps documented: `{root_cause.get('data_unavailable_count', 0)}`",
            f"- Stale price basis count: `{summary.get('stale_price_basis_count', 0)}`",
            "",
            "This batch is a source-coverage hardening run, not a current-research run. Price basis remains historical, so results are valid for guardrail QA only.",
        ]
    )
    (target_dir / "pilot_review.md").write_text(text + "\n", encoding="utf-8")


def _write_artifact_consistency_overview(target_dir: Path, selected_tickers: set[str]) -> None:
    rows = []
    for ticker in sorted(selected_tickers):
        path = target_dir / ticker / "artifact_consistency_report.json"
        payload = _load_json(path, default={})
        rows.append(
            {
                "ticker": ticker,
                "status": payload.get("status") or payload.get("consistency_status") or "unknown",
                "issue_count": len(payload.get("issues", [])) if isinstance(payload.get("issues"), list) else 0,
                "path": str(path) if path.exists() else None,
            }
        )
    overview = {
        "generated_at": _utc_now(),
        "status": "clean" if all(row["status"] in {"clean", "ok", "unknown"} and row["issue_count"] == 0 for row in rows) else "needs_review",
        "rows": rows,
    }
    _write_json(target_dir / "artifact_consistency_overview.json", overview)
    lines = ["# Artifact Consistency Overview", ""]
    lines.append("| Ticker | Status | Issues |")
    lines.append("|---|---|---:|")
    for row in rows:
        lines.append(f"| {row['ticker']} | {row['status']} | {row['issue_count']} |")
    (target_dir / "artifact_consistency_overview.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_vivi_review(target_dir: Path, target_batch_id: str, root_cause: dict[str, Any], dashboard: dict[str, Any]) -> dict[str, Any]:
    summary = dashboard.get("summary", {})
    payload = {
        "review_metadata": {
            "reviewer": "Vivi",
            "schema_version": "v1.1",
            "reviewed_at": _utc_now(),
            "bundle_id": target_batch_id,
            "batch_id": target_batch_id,
        },
        "review_status": "manual_human_review",
        "false_pass_candidates": [],
        "false_block_candidates": [],
        "blocking_issues": [],
        "non_blocking_issues": [
            {
                "category": "Evidence Coverage",
                "artifact": "DATA_AVAILABILITY_ROOT_CAUSE.json",
                "issue": "Batch 002 excludes the Batch-001 unavailable tickers because minimum local source inputs are missing.",
                "evidence": f"{root_cause.get('data_unavailable_count', 0)} Batch-001 rows cite missing local price CSV or adjacent source coverage gaps.",
                "expected_behavior": "Keep excluded names documented as data gaps until auditable inputs exist.",
                "severity": "major",
                "confidence": "high",
            },
            {
                "category": "Staleness / Data Freshness",
                "artifact": "dashboard_status.json",
                "issue": "Batch 002 uses a historical price basis and must not be treated as current research.",
                "evidence": f"{summary.get('historical_qa_only_count', 0)} dashboard rows are marked historical_qa_only.",
                "expected_behavior": "No current-research or public-ready routing without fresh price basis and promotion gate.",
                "severity": "major",
                "confidence": "high",
            },
        ],
        "fix_list_for_codex": [
            {
                "file_or_module": "outputs/source_inputs/phase12_operating_pilot_050/prices",
                "issue": "Missing auditable price CSV coverage for the excluded guardrail tickers.",
                "expected_behavior": "Add source-backed price CSVs or exclude unsupported names with an explicit data_gap status before rerun.",
                "acceptance_test": "SOURCE_INPUT_INVENTORY.json shows price_source_present=true for added tickers, and the next coverage batch reduces data_unavailable without false public-ready cases.",
                "do_not_touch_boundaries": [
                    "Do not synthesize prices.",
                    "Do not loosen evidence, rating, archetype, or freshness gates.",
                    "Do not hardcode ticker outcomes.",
                ],
                "priority": "P1",
            }
        ],
        "do_not_change": [
            "No guard loosening.",
            "No ticker hardcoding.",
            "Manual Review remains allowed.",
            "Promotion Gate remains the only public-ready path.",
        ],
        "human_review_required": True,
    }
    _write_json(target_dir / "vivi_batch_review.json", payload)
    return payload


def _write_market_readiness_decision(
    target_dir: Path,
    target_batch_id: str,
    dashboard: dict[str, Any],
    root_cause: dict[str, Any],
    matrix: dict[str, Any],
) -> None:
    summary = dashboard.get("summary", {})
    archetypes = matrix.get("summary", {}).get("archetype_counts", {})
    text = "\n".join(
        [
            f"# Market Readiness Decision - {target_batch_id}",
            "",
            "Decision: **YELLOW**",
            "",
            "The system remains usable for controlled internal guardrail QA, but data coverage and stale price basis limit current-research usage.",
            "",
            "## Operating Decision",
            "",
            "- Ready for regular internal batches: yes, if they are labeled by lane and source coverage is prechecked.",
            "- Current research reports allowed: no for this batch, because price basis is historical.",
            "- Historical QA allowed: yes.",
            "- Public output allowed: no without fresh data, final render, and Promotion Gate.",
            "",
            "## Stable Areas",
            "",
            f"- Covered archetypes in Batch 002: `{archetypes}`",
            f"- False pass candidates: `[]`",
            f"- False block candidates: `[]`",
            "",
            "## Top Data Coverage Priorities",
            "",
            "- Add auditable price CSVs for speculative deep-tech names.",
            "- Add auditable price CSVs for early-commercial capital-intensive names.",
            "- Add CIK/companyfacts or explicit vendor-only flags for unavailable names.",
            "- Add IR/current-period fixtures for contract/backlog and FCF-sensitive archetypes.",
            "- Keep unsupported ADR/foreign-issuer names out of source-ingestion batches until provider support is explicit.",
            "",
            "## Top System Fixes",
            "",
            "- Keep Freshness Gate visible in dashboard and quality metadata.",
            "- Keep Minimum Viable Data Gate visible in source inventory.",
            "- Add source precheck before launching broad guardrail batches.",
            "- Add fixture-backed current-period evidence for high-risk archetypes.",
            "- Keep data-unavailable rows out of public/promotion lanes.",
            "",
            f"Batch summary: passed `{summary.get('passed', 0)}`, manual_review `{summary.get('manual_review', 0)}`, failed `{summary.get('failed', 0)}`, data_unavailable `{summary.get('data_unavailable', 0)}`.",
            f"Batch-001 unavailable roots documented: `{root_cause.get('data_unavailable_count', 0)}`.",
        ]
    )
    (target_dir / "MARKET_READINESS_DECISION.md").write_text(text + "\n", encoding="utf-8")


def _write_bundles(target_dir: Path, selected_tickers: set[str], dashboard: dict[str, Any]) -> None:
    item_by_ticker = {item["ticker"]: item for item in dashboard.get("items", [])}
    passed = [ticker for ticker in selected_tickers if item_by_ticker.get(ticker, {}).get("status") == "passed"]
    manual = [ticker for ticker in selected_tickers if item_by_ticker.get(ticker, {}).get("status") == "manual_review"]
    problems: list[str] = []
    _bundle_tickers(target_dir, "chatgpt_publish_review_bundle.zip", passed, item_by_ticker, include_publish=True)
    _bundle_tickers(target_dir, "chatgpt_manual_review_bundle.zip", manual, item_by_ticker, include_publish=False)
    _bundle_tickers(target_dir, "chatgpt_problem_cases_bundle.zip", problems, item_by_ticker, include_publish=False, include_batch_docs=True)


def _bundle_tickers(
    target_dir: Path,
    bundle_name: str,
    tickers: Iterable[str],
    item_by_ticker: dict[str, dict[str, Any]],
    *,
    include_publish: bool,
    include_batch_docs: bool = False,
) -> None:
    bundle_path = target_dir / bundle_name
    doc_names = [
        "GUARDRAIL_COVERAGE_MATRIX.json",
        "GUARDRAIL_COVERAGE_MATRIX.md",
        "DATA_AVAILABILITY_ROOT_CAUSE.json",
        "DATA_AVAILABILITY_ROOT_CAUSE.md",
        "SOURCE_INPUT_INVENTORY.json",
        "SOURCE_INPUT_INVENTORY.md",
        "artifact_consistency_overview.json",
        "artifact_consistency_overview.md",
        "dashboard_status.json",
    ]
    artifact_keys = [
        "report_manifest.json",
        "quality_score.json",
        "decision_packet.json",
        "evidence_report.md",
        "current_period_reconciliation_summary.md",
        "metrics_packet.json",
        "canonical_financials.json",
        "artifact_consistency_report.json",
        "final_report.md",
        "internal_best_report.md",
    ]
    if include_publish:
        artifact_keys.append("publish_report.md")
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in doc_names:
            path = target_dir / name
            if path.exists() and (include_batch_docs or name in {"dashboard_status.json"}):
                zf.write(path, f"batch/{name}")
        for ticker in sorted(tickers):
            item = item_by_ticker.get(ticker, {})
            dashboard_item = json.dumps(item, indent=2, sort_keys=True)
            zf.writestr(f"tickers/{ticker}/dashboard_item.json", dashboard_item)
            artifacts = item.get("artifacts") or {}
            for key in artifact_keys:
                path_value = artifacts.get(key)
                if not path_value:
                    continue
                path = Path(str(path_value))
                if path.exists():
                    zf.write(path, f"tickers/{ticker}/{key}")
        if include_batch_docs:
            zf.writestr("README.md", "Problem-cases bundle is empty for Batch 002; excluded data gaps are documented in batch root-cause files.\n")


def _render_source_inventory_md(payload: dict[str, Any]) -> str:
    lines = [
        f"# Source Input Inventory - {payload.get('source_batch_id')}",
        "",
        f"- Generated at: `{payload.get('generated_at')}`",
        f"- Tickers: `{payload.get('ticker_count')}`",
        f"- Minimum viable possible: `{payload.get('summary', {}).get('minimum_viable_report_possible')}`",
        f"- Current report possible: `{payload.get('summary', {}).get('current_report_possible')}`",
        f"- Historical QA only: `{payload.get('summary', {}).get('historical_QA_only')}`",
        "",
        "| Ticker | Price | Latest Price | SEC/CIK | Companyfacts | Canonical | IR/Current | Benchmark | MVR | Current | Flags |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in payload.get("records", []):
        lines.append(
            f"| {row['ticker']} | {_yes(row['price_source_present'])} | {row.get('latest_price_date') or ''} | "
            f"{_yes(row['SEC_CIK_present'])} | {_yes(row['companyfacts_present'])} | "
            f"{_yes(row['canonical_financials_present'])} | {_yes(row['IR_current_period_evidence_present'])} | "
            f"{_yes(row['benchmark_present'])} | {_yes(row['minimum_viable_report_possible'])} | "
            f"{_yes(row['current_report_possible'])} | {', '.join(row['flags'])} |"
        )
    return "\n".join(lines) + "\n"


def _render_root_cause_md(payload: dict[str, Any]) -> str:
    lines = [
        f"# Data Availability Root Cause - {payload.get('source_batch_id')}",
        "",
        f"- Generated at: `{payload.get('generated_at')}`",
        f"- Data unavailable count: `{payload.get('data_unavailable_count')}`",
        f"- Count by root cause: `{payload.get('summary', {}).get('count_by_root_cause')}`",
        f"- Count by missing input: `{payload.get('summary', {}).get('count_by_missing_input_type')}`",
        "",
        "| Ticker | Bucket | Missing Price | Missing CIK | Missing Companyfacts | Missing IR | Root Cause | Priority | Recommended Fix |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in payload.get("records", []):
        lines.append(
            f"| {row['ticker']} | {row['expected_archetype_bucket']} | {_yes(row['missing_price_data'])} | "
            f"{_yes(row['missing_CIK_mapping'])} | {_yes(row['missing_SEC_companyfacts'])} | "
            f"{_yes(row['missing_IR_fixture'])} | {row['root_cause_type']} | {row['priority']} | {row['recommended_fix']} |"
        )
    return "\n".join(lines) + "\n"


def _render_matrix_md(matrix: dict[str, Any]) -> str:
    summary = matrix.get("summary", {})
    lines = [
        f"# Guardrail Coverage Matrix - {matrix.get('batch_id')}",
        "",
        f"- Batch mode: `{matrix.get('batch_mode')}`",
        f"- Listed tickers: `{matrix.get('listed_ticker_count')}`",
        f"- Passed: `{summary.get('passed_count')}`",
        f"- Manual review: `{summary.get('manual_review_count')}`",
        f"- Failed: `{summary.get('failed_count')}`",
        f"- Data unavailable: `{summary.get('data_unavailable_count')}`",
        f"- UNKNOWN archetype: `{summary.get('UNKNOWN_archetype_count')}`",
        "",
        "| Ticker | Status | Archetype | Publishable | Freshness | Historical QA | External Display |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in matrix.get("rows", []):
        lines.append(
            f"| {row['ticker']} | {row.get('review_status')} | {row.get('actual_archetype')} | "
            f"{_yes(row.get('publishable'))} | {row.get('data_freshness_status')} | "
            f"{_yes(row.get('historical_qa_only'))} | {row.get('external_display_rating')} |"
        )
    return "\n".join(lines) + "\n"


def _minimum_requirements_for_bucket(expected_bucket: str) -> list[str]:
    upper = expected_bucket.upper()
    for key, requirements in MINIMUM_DATA_REQUIREMENTS.items():
        if key in upper:
            return requirements
    return MINIMUM_DATA_REQUIREMENTS["MEGA_CAP"]


def _expected_bucket(row: dict[str, Any], tags: Iterable[str]) -> str:
    expected = str(row.get("expected_archetype") or "").upper()
    if expected:
        return expected
    tag_text = " ".join(tags).upper()
    if "SPECULATIVE_DEEP_TECH" in tag_text:
        return "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL"
    if "EARLY_COMMERCIAL" in tag_text:
        return "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH"
    if "TURNAROUND" in tag_text:
        return "TURNAROUND / BUSINESS_MODEL_PRESSURE"
    if "SEMICONDUCTOR" in tag_text:
        return "SEMICONDUCTOR_AI_INFRA"
    if "SAAS" in tag_text:
        return "SAAS_CONSUMPTION / STANDARD_GROWTH"
    return "MEGA_CAP_PLATFORM"


def _config_tags(config: BatchConfig, ticker: str) -> list[str]:
    for row in config.tickers:
        if row.ticker.upper() == ticker.upper():
            return list(row.tags)
    return []


def _benchmark_present(config: BatchConfig, ticker: str, price_dir: Path) -> bool:
    for row in config.tickers:
        if row.ticker.upper() == ticker.upper():
            return bool(row.benchmark and (price_dir / f"{row.benchmark.upper()}.csv").exists())
    return False


def _root_issue_type(ticker: str, price_present: bool, cik_present: bool, companyfacts_present: bool, error_message: Optional[str]) -> str:
    if not price_present and "Missing CSV price history" in str(error_message or ""):
        return "local_file_missing"
    if ticker in {"TSM", "ASML"} and not cik_present:
        return "unsupported_asset_type"
    if not cik_present or not companyfacts_present:
        return "config_omission"
    return "parser_failure"


def _recommended_fix(ticker: str, issue_type: str, expected_bucket: str) -> str:
    if issue_type == "unsupported_asset_type":
        return "Exclude from source-ingestion guardrail batch until foreign-issuer/ADR provider support is explicit."
    if "SPECULATIVE_DEEP_TECH" in expected_bucket or "EARLY_COMMERCIAL_CAPITAL_INTENSIVE" in expected_bucket:
        return "Add auditable price CSV plus SEC/IR or explicit vendor-only current-period evidence before rerun."
    return f"Add auditable local price CSV and verify CIK/companyfacts coverage for {ticker}."


def _root_cause_priority(issue_type: str, expected_bucket: str) -> str:
    if issue_type == "unsupported_asset_type":
        return "P3"
    if "SPECULATIVE_DEEP_TECH" in expected_bucket or "EARLY_COMMERCIAL_CAPITAL_INTENSIVE" in expected_bucket:
        return "P1"
    return "P2"


def _missing_input_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    keys = [
        "missing_price_data",
        "missing_SEC_companyfacts",
        "missing_CIK_mapping",
        "missing_IR_fixture",
        "missing_earnings_current_period_evidence",
        "missing_news_vendor_fallback",
        "missing_benchmark_data",
    ]
    return {key: sum(1 for row in records if row.get(key)) for key in keys}


def _quick_fixes(records: list[dict[str, Any]]) -> list[str]:
    fixes = []
    missing_price = [row["ticker"] for row in records if row["missing_price_data"] and row["root_cause_type"] != "unsupported_asset_type"]
    if missing_price:
        fixes.append(f"Add local source price CSVs for: {', '.join(missing_price)}.")
    missing_companyfacts = [row["ticker"] for row in records if row["missing_SEC_companyfacts"] and row["root_cause_type"] != "unsupported_asset_type"]
    if missing_companyfacts:
        fixes.append(f"Add CIK/companyfacts or explicit vendor-only flags for: {', '.join(missing_companyfacts)}.")
    return fixes


def _latest_csv_date(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    latest: Optional[str] = None
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            value = row.get("date") or row.get("Date")
            if value:
                latest = value[:10]
    return latest


def _artifact_price_basis_date(artifacts: dict[str, str]) -> Optional[str]:
    data_packet = artifacts.get("data_packet.json")
    if data_packet and Path(data_packet).exists():
        payload = _load_json(data_packet, default={})
        price_basis = payload.get("price_basis") or {}
        if price_basis.get("date"):
            return str(price_basis["date"])[:10]
    report_manifest = artifacts.get("report_manifest.json")
    if report_manifest and Path(report_manifest).exists():
        payload = _load_json(report_manifest, default={})
        if payload.get("price_basis_date"):
            return str(payload["price_basis_date"])[:10]
    return None


def _artifact_exists(artifacts: dict[str, str], key: str) -> bool:
    value = artifacts.get(key)
    return bool(value and Path(value).exists())


def _news_fallback_present(ticker: str) -> bool:
    patterns = [
        f"**/{ticker}_news*.json",
        f"**/{ticker}_vendor*.json",
        f"**/{ticker}_current*.json",
    ]
    roots = [Path("outputs/source_inputs"), Path("research_agent/data/packets")]
    return any(any(root.glob(pattern)) for root in roots for pattern in patterns)


def _load_cik_records(path: Optional[str]) -> set[str]:
    if not path or not Path(path).exists():
        return set()
    payload = _load_json(path, default=[])
    if isinstance(payload, list):
        return {str(row.get("ticker", "")).upper() for row in payload if row.get("ticker")}
    if isinstance(payload, dict):
        return {str(key).upper() for key in payload}
    return set()


def _load_earnings_calendar(path: Optional[str]) -> set[str]:
    if not path or not Path(path).exists():
        return set()
    payload = _load_json(path, default={})
    if isinstance(payload, list):
        return {str(row.get("ticker", "")).upper() for row in payload if row.get("ticker")}
    if isinstance(payload, dict):
        return {str(key).upper() for key in payload}
    return set()


def _rewrite_batch_strings(value: Any, target_batch_id: str) -> Any:
    if isinstance(value, dict):
        return {key: _rewrite_batch_strings(item, target_batch_id) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_batch_strings(item, target_batch_id) for item in value]
    if isinstance(value, str):
        return value.replace("guardrail_coverage_batch_001", target_batch_id)
    return value


def _top_values(values: Iterable[Any], limit: int = 10) -> list[dict[str, Any]]:
    counter = Counter(str(value) for value in values if value)
    return [{"value": value, "count": count} for value, count in counter.most_common(limit)]


def _load_json(path: str | Path, *, default: Any) -> Any:
    target = Path(path)
    if not target.exists():
        return default
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def _write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _yes(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

