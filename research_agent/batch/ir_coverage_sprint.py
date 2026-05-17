from __future__ import annotations

import json
import shutil
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_agent.batch import current_research_recovery as batch003
from research_agent.batch.batch_config import BatchConfig, BatchTickerConfig
from research_agent.batch.batch_manifest import BatchManifest, load_batch_manifest, save_batch_manifest
from research_agent.batch.batch_runner import BatchRunner
from research_agent.batch.dashboard_adapter import build_dashboard_status, save_dashboard_status
from research_agent.research_core.ingestion.source_registry import SourceRegistry, SourceRegistryEntry, save_source_registry


BATCH_ID = "guardrail_coverage_batch_004_ir_coverage"
AS_OF_DATE = "2026-05-17"
SOURCE_ROOT = Path("outputs/source_inputs") / BATCH_ID
BATCH_ROOT = Path("outputs/batches") / BATCH_ID
BATCH_003_ROOT = Path("outputs/batches/guardrail_coverage_batch_003_current_research")
BATCH_003_SOURCE_ROOT = Path("outputs/source_inputs/guardrail_coverage_batch_003_current_research")
SEC_USER_AGENT = batch003.SEC_USER_AGENT
TICKERS = list(batch003.CORE_UNIVERSE)

SEC_DERIVED_FIXTURE_TARGETS = {
    "NOW",
    "MDB",
    "NET",
    "ZS",
    "CRWD",
    "NVDA",
    "AMD",
    "QCOM",
    "MU",
    "MRVL",
    "INTC",
    "RGTI",
    "IONQ",
    "QBTS",
    "ASTS",
    "ACHR",
    "JOBY",
    "RIVN",
    "LCID",
    "PLUG",
}


def run_ir_coverage_sprint() -> dict[str, Any]:
    _point_batch003_helpers_at_batch004()
    if BATCH_ROOT.exists():
        shutil.rmtree(BATCH_ROOT)
    BATCH_ROOT.mkdir(parents=True, exist_ok=True)
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)

    missing_plan = _write_missing_fixture_plan()
    price_report = batch003._refresh_price_inputs(TICKERS, BATCH_ROOT, SOURCE_ROOT / "prices")
    sec_report = batch003._refresh_sec_inputs(TICKERS, BATCH_ROOT, SOURCE_ROOT)
    ir_report = _prepare_ir_fixtures(sec_report, missing_plan)
    fixture_validation = _write_fixture_validation(ir_report)
    universe = _write_universe(price_report, sec_report, ir_report)
    _write_source_registries(universe["included_tickers"], sec_report, ir_report, price_report)
    config_path = _write_batch_config(universe["included_tickers"])

    manifest = BatchRunner(BatchConfig.model_validate(_load_json(config_path, default={}))).run()
    manifest = batch003._post_process_batch_outputs(manifest, price_report, sec_report, ir_report, universe)
    dashboard = build_dashboard_status(manifest)
    save_dashboard_status(dashboard, BATCH_ROOT / "dashboard_status.json")

    matrix = batch003._write_guardrail_matrix(dashboard, universe)
    source_inventory = batch003._write_batch_source_inventory(dashboard, price_report, sec_report, ir_report, universe)
    current_period = _write_current_period_coverage(dashboard, sec_report, ir_report, fixture_validation)
    consistency = batch003._write_artifact_consistency_overview(dashboard)
    data_root = _write_empty_data_root(dashboard)
    vivi = batch003._write_vivi_review(dashboard, matrix, data_root, source_inventory, consistency)
    market = _write_market_readiness(dashboard, matrix, price_report, ir_report, vivi, current_period)
    backlog = _write_data_ops_backlog(current_period, missing_plan)
    bundles = _write_bundles(dashboard)

    return {
        "missing_plan": missing_plan,
        "price_report": price_report,
        "sec_report": sec_report,
        "ir_report": ir_report,
        "fixture_validation": fixture_validation,
        "universe": universe,
        "dashboard": dashboard,
        "matrix": matrix,
        "source_inventory": source_inventory,
        "current_period": current_period,
        "consistency": consistency,
        "bundles": bundles,
        "vivi": vivi,
        "market": market,
        "backlog": backlog,
    }


def _point_batch003_helpers_at_batch004() -> None:
    batch003.BATCH_ID = BATCH_ID
    batch003.AS_OF_DATE = AS_OF_DATE
    batch003.SOURCE_ROOT = SOURCE_ROOT
    batch003.BATCH_ROOT = BATCH_ROOT


def _write_missing_fixture_plan() -> dict[str, Any]:
    ir_priority = _load_json(BATCH_003_ROOT / "IR_FIXTURE_PRIORITY.json", default={})
    inventory = _load_json(BATCH_003_ROOT / "SOURCE_INPUT_INVENTORY.json", default={})
    dashboard = _load_json(BATCH_003_ROOT / "dashboard_status.json", default={})
    inventory_by_ticker = {row["ticker"]: row for row in inventory.get("records", [])}
    dashboard_by_ticker = {row["ticker"]: row for row in dashboard.get("items", [])}
    records: list[dict[str, Any]] = []
    for row in ir_priority.get("rows", []):
        if row.get("IR_fixture_available"):
            continue
        ticker = row["ticker"]
        item = dashboard_by_ticker.get(ticker, {})
        inv = inventory_by_ticker.get(ticker, {})
        priority = _fixture_priority(ticker)
        current_kpis_required = ticker in {
            "RGTI",
            "IONQ",
            "QBTS",
            "RKLB",
            "ASTS",
            "ACHR",
            "JOBY",
            "NVDA",
            "QCOM",
            "MU",
            "AMD",
            "AVGO",
            "CRWD",
            "MDB",
            "NET",
        }
        records.append(
            {
                "ticker": ticker,
                "company_name": _company_name(item),
                "archetype": item.get("company_archetype") or "UNKNOWN",
                "latest_available_fiscal_period_needed": "latest SEC CompanyFacts / latest 10-Q or 10-K period",
                "missing": {
                    "earnings_release": True,
                    "10_Q": False,
                    "10_K": False,
                    "guidance": True,
                    "segment_KPIs": not bool(row.get("segment_KPI_available")),
                    "company_defined_FCF": not bool(row.get("company_defined_FCF_available")),
                },
                "SEC_CompanyFacts_already_covers_enough": bool(inv.get("companyfacts_present")),
                "IR_release_required": ticker in {"RGTI", "IONQ", "QBTS", "ASTS", "ACHR", "JOBY"},
                "current_period_KPIs_required_for_publish_manual_review_logic": current_kpis_required,
                "priority": priority,
                "recommended_action": _missing_fixture_action(ticker, priority, bool(inv.get("companyfacts_present"))),
            }
        )
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "source_batch": "guardrail_coverage_batch_003_current_research",
        "missing_fixture_count": len(records),
        "summary": {
            "count_by_priority": dict(Counter(row["priority"] for row in records)),
            "sec_derived_quick_fix_candidates": sum(1 for row in records if row["SEC_CompanyFacts_already_covers_enough"]),
            "ir_release_required_count": sum(1 for row in records if row["IR_release_required"]),
            "target_additional_fixtures": min(len(records), 20),
        },
        "records": records,
    }
    _write_json(BATCH_ROOT / "IR_MISSING_FIXTURE_PLAN.json", payload)
    (BATCH_ROOT / "IR_MISSING_FIXTURE_PLAN.md").write_text(_render_missing_fixture_plan_md(payload), encoding="utf-8")
    return payload


def _prepare_ir_fixtures(sec_report: dict[str, Any], missing_plan: dict[str, Any]) -> dict[str, Any]:
    ir_dir = SOURCE_ROOT / "ir_releases"
    ir_dir.mkdir(parents=True, exist_ok=True)
    if BATCH_003_SOURCE_ROOT.exists():
        for source in (BATCH_003_SOURCE_ROOT / "ir_releases").glob("*.json"):
            payload = _load_json(source, default={})
            payload.setdefault("source_confidence", "high")
            payload.setdefault("source_url", payload.get("url"))
            payload.setdefault("coverage_note", "Carried forward from Batch 003 sourced current-period fixture.")
            _write_json(ir_dir / source.name, payload)
    sec_by_ticker = {row["ticker"]: row for row in sec_report.get("rows", [])}
    added = []
    for row in missing_plan["records"]:
        ticker = row["ticker"]
        if ticker not in SEC_DERIVED_FIXTURE_TARGETS:
            continue
        sec = sec_by_ticker.get(ticker, {})
        if not sec.get("companyfacts_present"):
            continue
        metrics_packet = _load_json(Path("research_agent/data/packets") / ticker / AS_OF_DATE / "metrics_packet.json", default={})
        fixture = _sec_derived_fixture(ticker, sec, metrics_packet)
        if not fixture["metrics"]:
            continue
        _write_json(ir_dir / f"{ticker}.json", fixture)
        added.append(ticker)

    rows = []
    for ticker in TICKERS:
        path = ir_dir / f"{ticker}.json"
        payload = _load_json(path, default={}) if path.exists() else {}
        metrics = payload.get("metrics") or []
        metric_names = {metric.get("metric_name") for metric in metrics}
        metric_text = json.dumps(payload).lower()
        rows.append(
            {
                "ticker": ticker,
                "IR_fixture_available": path.exists(),
                "latest_earnings_release_available": path.exists() and payload.get("source_type") in {"earnings_release", "company_ir", "official_press_release"},
                "current_period_KPIs_available": bool(metrics),
                "company_defined_FCF_available": any(
                    metric.get("metric_name") in {"free_cash_flow", "adjusted_free_cash_flow"}
                    and str(metric.get("basis")).lower() == "company_defined"
                    for metric in metrics
                ),
                "sec_derived_FCF_available": any(
                    metric.get("metric_name") == "free_cash_flow"
                    and "sec_derived_fcf" in (metric.get("supports_metrics") or [])
                    for metric in metrics
                ),
                "guidance_available": "guidance" in metric_text and "no company guidance" not in metric_text,
                "segment_KPI_available": any(
                    term in str(name)
                    for name in metric_names
                    for term in ["cloud", "ai", "segment", "product", "space_systems", "launch_services", "net_revenue_retention"]
                ),
                "priority": _fixture_priority(ticker),
                "action": "Use sourced fixture as current-period evidence; do not infer missing guidance." if path.exists() else "Keep current-period gap visible; do not publish without evidence.",
                "fixture_path": str(path) if path.exists() else None,
                "fixture_source_type": payload.get("source_type"),
                "source_form": payload.get("source_form"),
                "added_in_batch_004": ticker in added,
            }
        )
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "ir_release_dir": str(ir_dir),
        "summary": {
            "prioritized_count": len(rows),
            "fixture_available_count": sum(1 for row in rows if row["IR_fixture_available"]),
            "missing_fixture_count": sum(1 for row in rows if not row["IR_fixture_available"]),
            "fixtures_added_in_batch_004": len(added),
            "added_tickers": sorted(added),
        },
        "rows": rows,
    }
    _write_json(BATCH_ROOT / "IR_FIXTURE_PRIORITY.json", payload)
    (BATCH_ROOT / "IR_FIXTURE_PRIORITY.md").write_text(_render_ir_priority_md(payload), encoding="utf-8")
    return payload


def _sec_derived_fixture(ticker: str, sec: dict[str, Any], metrics_packet: dict[str, Any]) -> dict[str, Any]:
    fundamentals = metrics_packet.get("fundamentals") or {}
    cik = str(sec.get("cik") or "").zfill(10)
    report_date = sec.get("latest_filing_date") or AS_OF_DATE
    source_id = f"{ticker}_SEC_CURRENT_PERIOD_COMPANYFACTS_{report_date}".replace("-", "_")
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    metrics: list[dict[str, Any]] = []
    metric_specs = [
        ("revenue", "revenue_ttm", "income_statement", "ttm", "gaap", "revenue"),
        ("operating_cash_flow", "operating_cash_flow_ttm", "cash_flow", "ttm", "gaap", "operating cash flow"),
        ("free_cash_flow", "free_cash_flow_ttm", "cash_flow", "ttm", "gaap", "SEC-derived free cash flow"),
        ("sbc", "sbc_ttm", "cash_flow", "ttm", "gaap", "stock-based compensation"),
        ("cash_and_equivalents", "cash_and_equivalents", "balance_sheet", "instant", "gaap", "cash and equivalents"),
        ("marketable_securities", "marketable_securities", "balance_sheet", "instant", "gaap", "marketable securities"),
        ("total_debt", "total_debt", "balance_sheet", "instant", "gaap", "total debt"),
    ]
    for metric_name, source_key, statement_type, period_bucket, basis, label in metric_specs:
        value = fundamentals.get(source_key)
        if value is None:
            continue
        metrics.append(
            {
                "metric_name": metric_name,
                "value": value,
                "unit": "usd",
                "period": "latest_companyfacts_ttm" if period_bucket == "ttm" else "latest_companyfacts_instant",
                "fiscal_year": None,
                "fiscal_period": "latest",
                "period_bucket": period_bucket,
                "basis": basis,
                "statement_type": statement_type,
                "date": report_date,
                "end_date": report_date,
                "supports_metrics": _supports_metrics(metric_name, basis),
                "statement": f"{ticker} {label} is sourced from SEC CompanyFacts / latest filing context as of {report_date}.",
                "reconciliation_note": "SEC-derived current-period fixture generated from audited SEC CompanyFacts cache; no company guidance inferred.",
            }
        )
    return {
        "source_id": source_id,
        "source_type": "sec_filing",
        "source_form": "SEC_10Q_or_10K_companyfacts_current_period",
        "source_url": url,
        "url": url,
        "local_source_path": sec.get("companyfacts_path"),
        "retrieved_at": _utc_now(),
        "period": "latest_companyfacts_ttm",
        "fiscal_period": "latest",
        "report_date": report_date,
        "source_confidence": "high",
        "coverage_type": "SEC-derived current-period fixture",
        "text": "SEC CompanyFacts-derived current-period metrics. No company guidance included; no consensus data included.",
        "metrics": metrics,
    }


def _supports_metrics(metric_name: str, basis: str) -> list[str]:
    if metric_name == "free_cash_flow":
        return ["free_cash_flow", "free_cash_flow_ttm", "sec_derived_fcf"]
    mapping = {
        "revenue": ["revenue", "revenue_ttm"],
        "operating_cash_flow": ["operating_cash_flow", "operating_cash_flow_ttm"],
        "sbc": ["sbc", "sbc_ttm"],
        "cash_and_equivalents": ["cash_and_equivalents", "cash", "cash_and_investments"],
        "marketable_securities": ["marketable_securities", "cash_and_investments"],
        "total_debt": ["total_debt", "debt", "net_cash"],
    }
    return mapping.get(metric_name, [metric_name])


def _write_fixture_validation(ir_report: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for row in ir_report["rows"]:
        path_value = row.get("fixture_path")
        if not path_value:
            rows.append(
                {
                    "ticker": row["ticker"],
                    "status": "missing",
                    "fixture_path": None,
                    "issues": ["fixture missing"],
                    "evidence_item_generatable": False,
                }
            )
            continue
        payload = _load_json(path_value, default={})
        issues = []
        metrics = payload.get("metrics") or []
        if not payload.get("source_id"):
            issues.append("missing source_id")
        if payload.get("source_type") not in {"company_ir", "earnings_release", "sec_filing", "official_press_release"}:
            issues.append("unsupported source_type")
        if not (payload.get("source_url") or payload.get("url") or payload.get("local_source_path")):
            issues.append("missing source_url_or_local_source_path")
        if not (payload.get("report_date") or payload.get("retrieved_at")):
            issues.append("missing source date")
        if not payload.get("period"):
            issues.append("missing period")
        if not payload.get("source_confidence"):
            issues.append("missing source_confidence")
        payload_text = json.dumps(payload).lower()
        if (
            "consensus" in payload_text
            and "guidance" in payload_text
            and "no company guidance" not in payload_text
            and "no consensus" not in payload_text
        ):
            issues.append("guidance_consensus_mixing_review")
        for metric in metrics:
            if metric.get("metric_name") in {"free_cash_flow", "adjusted_free_cash_flow"} and not metric.get("basis"):
                issues.append("fcf basis missing")
            if metric.get("metric_name") == "free_cash_flow" and "sec_derived_fcf" in (metric.get("supports_metrics") or []) and "company_defined_fcf" in (metric.get("supports_metrics") or []):
                issues.append("sec_derived_fcf_marked_company_defined")
        status = "valid" if not issues else "needs_review"
        rows.append(
            {
                "ticker": row["ticker"],
                "status": status,
                "fixture_path": path_value,
                "source_type": payload.get("source_type"),
                "source_form": payload.get("source_form"),
                "metric_count": len(metrics),
                "issues": sorted(set(issues)),
                "evidence_item_generatable": bool(metrics and status in {"valid", "needs_review"}),
                "added_in_batch_004": row.get("added_in_batch_004"),
            }
        )
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "summary": {
            "valid_count": sum(1 for row in rows if row["status"] == "valid"),
            "needs_review_count": sum(1 for row in rows if row["status"] == "needs_review"),
            "rejected_count": sum(1 for row in rows if row["status"] == "rejected"),
            "missing_count": sum(1 for row in rows if row["status"] == "missing"),
            "valid_added_count": sum(1 for row in rows if row["status"] == "valid" and row.get("added_in_batch_004")),
        },
        "rows": rows,
    }
    _write_json(BATCH_ROOT / "IR_FIXTURE_VALIDATION.json", payload)
    (BATCH_ROOT / "IR_FIXTURE_VALIDATION.md").write_text(_render_fixture_validation_md(payload), encoding="utf-8")
    return payload


def _write_universe(price_report: dict[str, Any], sec_report: dict[str, Any], ir_report: dict[str, Any]) -> dict[str, Any]:
    price_by_ticker = {row["ticker"]: row for row in price_report["rows"]}
    sec_by_ticker = {row["ticker"]: row for row in sec_report["rows"]}
    ir_by_ticker = {row["ticker"]: row for row in ir_report["rows"]}
    records = []
    for ticker in TICKERS:
        price = price_by_ticker.get(ticker, {})
        sec = sec_by_ticker.get(ticker, {})
        ir = ir_by_ticker.get(ticker, {})
        records.append(
            {
                "ticker": ticker,
                "benchmark": batch003._benchmark_for(ticker),
                "expected_archetype_bucket": batch003._expected_archetype(ticker),
                "minimum_viable_data": bool(price.get("current_report_allowed") and sec.get("cik_present") and sec.get("companyfacts_present")),
                "fresh_price": bool(price.get("current_report_allowed")),
                "sec_companyfacts": bool(sec.get("companyfacts_present")),
                "current_period_fixture": bool(ir.get("IR_fixture_available")),
                "include_reason": batch003._include_reason(ticker),
            }
        )
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "included_ticker_count": len(records),
        "included_tickers": [row["ticker"] for row in records],
        "excluded_tickers": [],
        "summary": {
            "minimum_viable_count": sum(1 for row in records if row["minimum_viable_data"]),
            "fresh_price_count": sum(1 for row in records if row["fresh_price"]),
            "sec_companyfacts_count": sum(1 for row in records if row["sec_companyfacts"]),
            "current_period_fixture_count": sum(1 for row in records if row["current_period_fixture"]),
        },
        "records": records,
    }
    _write_json(BATCH_ROOT / "BATCH_004_UNIVERSE.json", payload)
    (BATCH_ROOT / "BATCH_004_UNIVERSE.md").write_text(_render_universe_md(payload), encoding="utf-8")
    return payload


def _write_source_registries(
    tickers: list[str],
    sec_report: dict[str, Any],
    ir_report: dict[str, Any],
    price_report: dict[str, Any],
) -> None:
    sec_by_ticker = {row["ticker"]: row for row in sec_report["rows"]}
    ir_by_ticker = {row["ticker"]: row for row in ir_report["rows"]}
    price_by_ticker = {row["ticker"]: row for row in price_report["rows"]}
    for ticker in tickers:
        sources = []
        sec = sec_by_ticker.get(ticker, {})
        if sec.get("cik") and sec.get("companyfacts_present"):
            sources.append(
                SourceRegistryEntry(
                    source_id=f"{ticker}_SEC_COMPANYFACTS_{sec['cik']}",
                    ticker=ticker,
                    source_type="sec_filing",
                    authority_rank=1,
                    url=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(sec['cik']).zfill(10)}.json",
                    retrieved_at=_utc_now(),
                    used_for=["revenue", "financial", "cash", "operating_income", "free_cash_flow", "fcf", "sbc", "debt", "eps"],
                )
            )
        ir = ir_by_ticker.get(ticker, {})
        if ir.get("IR_fixture_available"):
            fixture = _load_json(ir.get("fixture_path"), default={})
            fixture_source_type = fixture.get("source_type") or "sec_filing"
            registry_source_type = "company_ir" if fixture_source_type in {"company_ir", "earnings_release", "official_press_release"} else fixture_source_type
            sources.append(
                SourceRegistryEntry(
                    source_id=fixture.get("source_id") or f"{ticker}_CURRENT_PERIOD_FIXTURE",
                    ticker=ticker,
                    source_type=registry_source_type,
                    authority_rank=1,
                    url=fixture.get("source_url") or fixture.get("url"),
                    retrieved_at=_utc_now(),
                    used_for=_fixture_used_for(ticker, fixture),
                )
            )
        price = price_by_ticker.get(ticker, {})
        if price.get("csv_path"):
            sources.append(
                SourceRegistryEntry(
                    source_id=f"{ticker}_YAHOO_CHART_PRICE_CSV",
                    ticker=ticker,
                    source_type="exchange_ohlcv",
                    authority_rank=2,
                    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                    retrieved_at=_utc_now(),
                    used_for=["price", "volume", "technical_indicators"],
                )
            )
        save_source_registry(
            SourceRegistry(registry_id=f"{ticker}_{AS_OF_DATE}", sources=sources),
            Path("research_agent/data/packets") / f"{ticker}_{AS_OF_DATE}_source_registry.json",
        )


def _fixture_used_for(ticker: str, fixture: dict[str, Any]) -> list[str]:
    used = {"financial", "current_period_kpis"}
    for metric in fixture.get("metrics") or []:
        name = str(metric.get("metric_name") or "")
        used.add(name)
        if name in {"revenue", "current_q_revenue"}:
            used.add("revenue")
        if "cash" in name:
            used.add("cash")
        if "free_cash_flow" in name:
            used.add("fcf")
            used.add("free_cash_flow")
        if name == "sbc":
            used.add("sbc")
        if "debt" in name:
            used.add("debt")
    if ticker == "RKLB":
        used.update({"backlog", "contract_backlog", "contracted_missions", "launch_cadence", "electron_execution", "neutron_development_risk", "space_systems", "launch_services", "product_platform_still_scaling", "execution_milestone_risk"})
    if fixture.get("source_type") == "sec_filing":
        used.add("sec_derived_current_period")
    return sorted(used)


def _write_batch_config(tickers: list[str]) -> Path:
    configs = []
    for ticker in tickers:
        tags = ["guardrail_coverage_004_ir_coverage"]
        for tag, tag_tickers in batch003.TAGS_BY_BUCKET.items():
            if ticker in tag_tickers:
                tags.append(tag)
        configs.append(
            BatchTickerConfig(
                ticker=ticker,
                mode="source_ingestion_mode",
                priority="normal",
                benchmark=batch003._benchmark_for(ticker),
                tags=tags,
            ).model_dump(mode="json")
        )
    payload = {
        "batch_id": BATCH_ID,
        "as_of_date": AS_OF_DATE,
        "batch_mode": "current_research",
        "freshness_reference_date": AS_OF_DATE,
        "freshness_max_trading_days": 2,
        "max_parallel_jobs": 1,
        "output_dir": "outputs/batches",
        "pipeline_version": BATCH_ID,
        "model_provider": "deterministic",
        "model_name": "research_agent_v0.1.0",
        "price_csv_dir": str(SOURCE_ROOT / "prices"),
        "price_start_date": "2024-01-01",
        "cik_records_path": str(SOURCE_ROOT / "cik_records.json"),
        "sec_companyfacts_dir": str(SOURCE_ROOT / "sec_companyfacts"),
        "sec_user_agent": SEC_USER_AGENT,
        "ir_release_dir": str(SOURCE_ROOT / "ir_releases"),
        "tickers": configs,
    }
    path = Path("outputs/batches") / f"{BATCH_ID}_config.json"
    _write_json(path, payload)
    return path


def _write_current_period_coverage(
    dashboard: dict[str, Any],
    sec_report: dict[str, Any],
    ir_report: dict[str, Any],
    fixture_validation: dict[str, Any],
) -> dict[str, Any]:
    sec_by_ticker = {row["ticker"]: row for row in sec_report["rows"]}
    ir_by_ticker = {row["ticker"]: row for row in ir_report["rows"]}
    validation_by_ticker = {row["ticker"]: row for row in fixture_validation["rows"]}
    rows = []
    for item in dashboard["items"]:
        ticker = item["ticker"]
        ir = ir_by_ticker.get(ticker, {})
        sec = sec_by_ticker.get(ticker, {})
        validation = validation_by_ticker.get(ticker, {})
        ready = bool(ir.get("IR_fixture_available") and validation.get("status") in {"valid", "needs_review"})
        rows.append(
            {
                "ticker": ticker,
                "has_current_ir_fixture": bool(ir.get("IR_fixture_available")),
                "has_current_sec_evidence": bool(sec.get("current_period_primary_evidence")),
                "has_company_defined_fcf": bool(ir.get("company_defined_FCF_available")),
                "has_sec_derived_fcf": bool(ir.get("sec_derived_FCF_available")),
                "has_guidance": bool(ir.get("guidance_available")),
                "has_segment_kpis": bool(ir.get("segment_KPI_available")),
                "current_period_context_ready": ready,
                "publish_candidate_possible": bool(item.get("publishable") and ready),
                "manual_review_reason_if_not": "" if ready else "missing_current_period_fixture",
                "review_status": item.get("status"),
                "company_archetype": item.get("company_archetype"),
            }
        )
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "summary": {
            "ticker_count": len(rows),
            "current_ir_fixture_count": sum(1 for row in rows if row["has_current_ir_fixture"]),
            "current_period_context_ready_count": sum(1 for row in rows if row["current_period_context_ready"]),
            "company_defined_fcf_count": sum(1 for row in rows if row["has_company_defined_fcf"]),
            "sec_derived_fcf_count": sum(1 for row in rows if row["has_sec_derived_fcf"]),
            "guidance_count": sum(1 for row in rows if row["has_guidance"]),
            "segment_kpi_count": sum(1 for row in rows if row["has_segment_kpis"]),
        },
        "rows": rows,
    }
    _write_json(BATCH_ROOT / "CURRENT_PERIOD_COVERAGE_REPORT.json", payload)
    (BATCH_ROOT / "CURRENT_PERIOD_COVERAGE_REPORT.md").write_text(_render_current_period_md(payload), encoding="utf-8")
    return payload


def _write_empty_data_root(dashboard: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "ticker": item["ticker"],
            "root_cause_type": item.get("failure_type") or "data_gap",
            "error_message": item.get("error_message"),
            "recommended_fix": "Inspect failed/data_unavailable ticker; do not mark publishable.",
        }
        for item in dashboard["items"]
        if item.get("status") in {"failed", "data_unavailable"}
    ]
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "data_unavailable_count": sum(1 for item in dashboard["items"] if item.get("status") == "data_unavailable"),
        "failed_count": sum(1 for item in dashboard["items"] if item.get("status") == "failed"),
        "summary": {"count_by_root_cause": dict(Counter(row["root_cause_type"] for row in rows))},
        "records": rows,
    }
    _write_json(BATCH_ROOT / "DATA_AVAILABILITY_ROOT_CAUSE.json", payload)
    (BATCH_ROOT / "DATA_AVAILABILITY_ROOT_CAUSE.md").write_text("# Data Availability Root Cause - Batch 004\n\nNo data unavailable records.\n" if not rows else json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _write_bundles(dashboard: dict[str, Any]) -> dict[str, str]:
    paths = batch003._write_bundles(dashboard)
    batch_docs = [
        "IR_MISSING_FIXTURE_PLAN.json",
        "IR_MISSING_FIXTURE_PLAN.md",
        "IR_FIXTURE_VALIDATION.json",
        "IR_FIXTURE_VALIDATION.md",
        "CURRENT_PERIOD_COVERAGE_REPORT.json",
        "CURRENT_PERIOD_COVERAGE_REPORT.md",
        "MARKET_READINESS_DECISION.json",
        "MARKET_READINESS_DECISION.md",
        "DATA_OPS_BACKLOG.json",
        "DATA_OPS_BACKLOG.md",
    ]
    for bundle_path in paths.values():
        with zipfile.ZipFile(bundle_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
            for name in batch_docs:
                path = BATCH_ROOT / name
                if path.exists():
                    zf.write(path, f"batch/{name}")
    return paths


def _write_market_readiness(
    dashboard: dict[str, Any],
    matrix: dict[str, Any],
    price_report: dict[str, Any],
    ir_report: dict[str, Any],
    vivi: dict[str, Any],
    current_period: dict[str, Any],
) -> dict[str, Any]:
    false_pass = matrix["summary"]["top_false_pass_candidates"]
    false_block = matrix["summary"]["top_false_block_candidates"]
    fixture_count = ir_report["summary"]["fixture_available_count"]
    stale_count = price_report["summary"].get("stale_count", 0)
    blocking = bool(false_pass or false_block or stale_count or dashboard["summary"].get("failed") or dashboard["summary"].get("data_unavailable"))
    if blocking:
        verdict = "RED"
    elif fixture_count >= 24 and vivi["review_status"] in {"pass", "manual_human_review"}:
        verdict = "GREEN"
    else:
        verdict = "YELLOW"
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "decision": verdict,
        "current_operating_readiness": "usable_with_review" if verdict in {"GREEN", "YELLOW"} else "blocked",
        "current_reports_can_be_used_internally": verdict in {"GREEN", "YELLOW"},
        "public_output_blocked": True,
        "ir_current_period_coverage": f"{fixture_count}/32",
        "top_5_data_coverage_priorities": _remaining_priorities(current_period)[:5],
        "top_5_system_fixes": ["No immediate P0/P1 system fix; remaining work is data ops coverage."] if verdict != "RED" else ["Inspect blocking false pass/false block/staleness issues before new coverage work."],
        "next_7_day_plan": [
            "Replace SEC-derived fixtures with direct IR/earnings-release fixtures for names where guidance or segment KPIs matter.",
            "Prioritize QCOM/NVDA/AMD/MU/INTC semi current-period release detail.",
            "Prioritize RGTI/IONQ/QBTS/ASTS/ACHR/JOBY direct company release or 10-Q extracts before public promotion.",
            "Keep Promotion Gate closed for all manual_review reports.",
            "Run a compact Batch 004 affected-subset regression after any new direct IR fixtures.",
        ],
    }
    _write_json(BATCH_ROOT / "MARKET_READINESS_DECISION.json", payload)
    (BATCH_ROOT / "MARKET_READINESS_DECISION.md").write_text(_render_market_md(payload), encoding="utf-8")
    return payload


def _write_data_ops_backlog(current_period: dict[str, Any], missing_plan: dict[str, Any]) -> dict[str, Any]:
    missing_by_ticker = {row["ticker"]: row for row in missing_plan["records"]}
    records = []
    for row in current_period["rows"]:
        plan = missing_by_ticker.get(row["ticker"], {})
        needs_direct_ir = row["ticker"] in {"RGTI", "IONQ", "QBTS", "ASTS", "ACHR", "JOBY", "QCOM", "NVDA", "AMD", "MU", "INTC"}
        if not needs_direct_ir and row["current_period_context_ready"]:
            continue
        records.append(
            {
                "ticker": row["ticker"],
                "remaining_gap": "direct IR/earnings-release fixture preferred" if row["current_period_context_ready"] else "current-period fixture missing",
                "priority": plan.get("priority") or _fixture_priority(row["ticker"]),
                "estimated_effort": "medium" if needs_direct_ir else "low",
                "blocker_type": "source_collection" if needs_direct_ir else "none",
                "needed_for": "publish/manual_review/archetype" if needs_direct_ir else "archetype only",
                "next_action": "Fetch direct company IR/earnings release or 10-Q extract; do not infer guidance.",
            }
        )
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "remaining_count": len(records),
        "summary": {
            "count_by_priority": dict(Counter(row["priority"] for row in records)),
            "direct_ir_preferred_count": sum(1 for row in records if row["remaining_gap"] == "direct IR/earnings-release fixture preferred"),
        },
        "records": records,
        "next_7_day_plan": [
            "Replace SEC-derived semi fixtures with direct earnings release metrics where FCF/guidance is central.",
            "Add direct company releases for speculative/early-commercial names before any public promotion discussion.",
            "Keep all unresolved direct-IR gaps as manual_review or internal-only.",
        ],
    }
    _write_json(BATCH_ROOT / "DATA_OPS_BACKLOG.json", payload)
    (BATCH_ROOT / "DATA_OPS_BACKLOG.md").write_text(_render_backlog_md(payload), encoding="utf-8")
    return payload


def _fixture_priority(ticker: str) -> str:
    if ticker in {"NVDA", "QCOM", "RGTI", "IONQ", "QBTS"}:
        return "P0"
    if ticker in {"AMD", "MU", "MRVL", "INTC", "MDB", "NET", "CRWD", "ASTS", "ACHR", "JOBY"}:
        return "P1"
    if ticker in {"NOW", "ZS", "RIVN", "LCID", "PLUG"}:
        return "P2"
    return "P3"


def _missing_fixture_action(ticker: str, priority: str, companyfacts_ready: bool) -> str:
    if not companyfacts_ready:
        return "Keep data gap; do not create pseudo fixture."
    if priority in {"P0", "P1"}:
        return "Create SEC-derived current-period fixture now; prefer direct IR/earnings release later."
    return "Create SEC-derived fixture if coverage target needs it; otherwise document as lower priority."


def _company_name(item: dict[str, Any]) -> str | None:
    manifest_path = (item.get("artifacts") or {}).get("report_manifest.json")
    return _load_json(manifest_path, default={}).get("company_name") if manifest_path else None


def _remaining_priorities(current_period: dict[str, Any]) -> list[str]:
    priorities = []
    for row in current_period["rows"]:
        if not row["has_guidance"] and row["ticker"] in {"QCOM", "NVDA", "AMD", "MU", "INTC", "RGTI", "IONQ", "QBTS", "ASTS", "ACHR", "JOBY"}:
            priorities.append(f"{row['ticker']}: direct IR/guidance or explicit no-guidance evidence")
    return priorities or ["No critical remaining current-period fixture gaps; continue replacing SEC-derived fixtures with direct IR sources."]


def _render_missing_fixture_plan_md(payload: dict[str, Any]) -> str:
    lines = [
        "# IR Missing Fixture Plan",
        "",
        f"- Missing fixtures: `{payload['missing_fixture_count']}`",
        f"- SEC-derived quick-fix candidates: `{payload['summary']['sec_derived_quick_fix_candidates']}`",
        "",
        "| Ticker | Archetype | Priority | SEC Enough | IR Required | Action |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["records"]:
        lines.append(f"| {row['ticker']} | {row['archetype']} | {row['priority']} | {_yes(row['SEC_CompanyFacts_already_covers_enough'])} | {_yes(row['IR_release_required'])} | {row['recommended_action']} |")
    return "\n".join(lines) + "\n"


def _render_ir_priority_md(payload: dict[str, Any]) -> str:
    lines = [
        "# IR Fixture Priority - Batch 004",
        "",
        f"- Fixtures available: `{payload['summary']['fixture_available_count']}`",
        f"- Added in Batch 004: `{payload['summary']['fixtures_added_in_batch_004']}`",
        "",
        "| Ticker | Fixture | Source | Current KPIs | Co FCF | SEC FCF | Guidance | Segment | Priority |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(f"| {row['ticker']} | {_yes(row['IR_fixture_available'])} | {row.get('fixture_source_type') or ''} | {_yes(row['current_period_KPIs_available'])} | {_yes(row['company_defined_FCF_available'])} | {_yes(row['sec_derived_FCF_available'])} | {_yes(row['guidance_available'])} | {_yes(row['segment_KPI_available'])} | {row['priority']} |")
    return "\n".join(lines) + "\n"


def _render_fixture_validation_md(payload: dict[str, Any]) -> str:
    lines = [
        "# IR Fixture Validation",
        "",
        f"- Valid: `{payload['summary']['valid_count']}`",
        f"- Needs review: `{payload['summary']['needs_review_count']}`",
        f"- Rejected: `{payload['summary']['rejected_count']}`",
        "",
        "| Ticker | Status | Source | Metrics | Issues |",
        "|---|---|---|---:|---|",
    ]
    for row in payload["rows"]:
        lines.append(f"| {row['ticker']} | {row['status']} | {row.get('source_type') or ''} | {row.get('metric_count', 0)} | {', '.join(row.get('issues') or [])} |")
    return "\n".join(lines) + "\n"


def _render_universe_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Batch 004 Universe",
        "",
        f"- Included ticker count: `{payload['included_ticker_count']}`",
        f"- Current-period fixture count: `{payload['summary']['current_period_fixture_count']}`",
        "",
        "| Ticker | Benchmark | MVD | Fresh Price | SEC CompanyFacts | Current Fixture |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["records"]:
        lines.append(f"| {row['ticker']} | {row['benchmark']} | {_yes(row['minimum_viable_data'])} | {_yes(row['fresh_price'])} | {_yes(row['sec_companyfacts'])} | {_yes(row['current_period_fixture'])} |")
    return "\n".join(lines) + "\n"


def _render_current_period_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Current Period Coverage Report",
        "",
        f"- Current fixture coverage: `{payload['summary']['current_ir_fixture_count']}/{payload['summary']['ticker_count']}`",
        f"- Context ready: `{payload['summary']['current_period_context_ready_count']}/{payload['summary']['ticker_count']}`",
        "",
        "| Ticker | Fixture | SEC | Co FCF | SEC FCF | Guidance | Segment | Ready |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(f"| {row['ticker']} | {_yes(row['has_current_ir_fixture'])} | {_yes(row['has_current_sec_evidence'])} | {_yes(row['has_company_defined_fcf'])} | {_yes(row['has_sec_derived_fcf'])} | {_yes(row['has_guidance'])} | {_yes(row['has_segment_kpis'])} | {_yes(row['current_period_context_ready'])} |")
    return "\n".join(lines) + "\n"


def _render_market_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Market Readiness Decision - Batch 004",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- IR/current-period coverage: `{payload['ir_current_period_coverage']}`",
        f"- Public output blocked: `{payload['public_output_blocked']}`",
        "",
        "## Top Data Coverage Priorities",
    ]
    lines.extend(f"- {item}" for item in payload["top_5_data_coverage_priorities"])
    lines.extend(["", "## Next 7 Days"])
    lines.extend(f"- {item}" for item in payload["next_7_day_plan"])
    return "\n".join(lines) + "\n"


def _render_backlog_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Data Ops Backlog",
        "",
        f"- Remaining count: `{payload['remaining_count']}`",
        "",
        "| Ticker | Gap | Priority | Effort | Needed For | Next Action |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["records"]:
        lines.append(f"| {row['ticker']} | {row['remaining_gap']} | {row['priority']} | {row['estimated_effort']} | {row['needed_for']} | {row['next_action']} |")
    return "\n".join(lines) + "\n"


def _load_json(path: str | Path | None, *, default: Any) -> Any:
    if not path:
        return default
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


if __name__ == "__main__":
    result = run_ir_coverage_sprint()
    print(
        json.dumps(
            {
                "batch_id": BATCH_ID,
                "market": result["market"]["decision"],
                "dashboard_summary": result["dashboard"]["summary"],
                "ir_summary": result["ir_report"]["summary"],
                "fixture_validation": result["fixture_validation"]["summary"],
                "current_period": result["current_period"]["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
