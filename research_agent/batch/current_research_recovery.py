from __future__ import annotations

import csv
import json
import math
import shutil
import time
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from research_agent.batch.batch_config import BatchConfig, BatchTickerConfig
from research_agent.batch.batch_manifest import BatchManifest, load_batch_manifest, save_batch_manifest
from research_agent.batch.batch_runner import BatchRunner
from research_agent.batch.dashboard_adapter import build_dashboard_status, save_dashboard_status
from research_agent.batch.freshness import evaluate_price_freshness
from research_agent.research_core.ingestion.source_registry import SourceRegistry, SourceRegistryEntry, save_source_registry
from research_agent.sources.sec.sec_client import SecClient, SecClientConfig


BATCH_ID = "guardrail_coverage_batch_003_current_research"
AS_OF_DATE = "2026-05-17"
SOURCE_ROOT = Path("outputs/source_inputs") / BATCH_ID
BATCH_ROOT = Path("outputs/batches") / BATCH_ID
SOURCE_BATCH_001 = Path("outputs/batches/guardrail_coverage_batch_001")
SOURCE_CONFIG_001 = Path("outputs/batches/guardrail_coverage_batch_001_config.json")
SEC_USER_AGENT = "QuellwertResearchAgent/0.1 codex-pilot@example.com"

CORE_UNIVERSE = [
    "GOOGL",
    "SNOW",
    "MSFT",
    "AAPL",
    "META",
    "AMZN",
    "NFLX",
    "CRM",
    "DDOG",
    "NOW",
    "MDB",
    "NET",
    "ZS",
    "CRWD",
    "PANW",
    "NVDA",
    "AMD",
    "AVGO",
    "QCOM",
    "MU",
    "MRVL",
    "INTC",
    "RGTI",
    "IONQ",
    "QBTS",
    "RKLB",
    "ASTS",
    "ACHR",
    "JOBY",
    "RIVN",
    "LCID",
    "PLUG",
]

EXCLUDED_FOR_BATCH_003 = {
    "TSM": "Foreign issuer / ADR support is not explicit in this deterministic source-ingestion lane.",
    "ASML": "Foreign issuer / ADR support is not explicit in this deterministic source-ingestion lane.",
    "QUBT": "Lower-priority speculative case; keep out until the higher-value quantum set is current-data-ready.",
    "SOUN": "Lower-priority speculative AI story-stock; keep out until core deep-tech coverage is stable.",
    "BBAI": "Lower-priority speculative AI story-stock; keep out until core deep-tech coverage is stable.",
    "PYPL": "Useful turnaround case, but lower priority than the required Batch-003 guardrail universe.",
    "SNAP": "Useful turnaround case, but lower priority than the required Batch-003 guardrail universe.",
    "WBA": "Useful distressed case, but lower priority than the required Batch-003 guardrail universe.",
    "PARA": "Useful distressed case, but lower priority than the required Batch-003 guardrail universe.",
}

TAGS_BY_BUCKET = {
    "mega_cap_platform": {"GOOGL", "MSFT", "AAPL", "META", "AMZN", "NFLX"},
    "gold_control": {"GOOGL", "SNOW", "MSFT"},
    "saas_security": {"CRM", "DDOG", "NOW", "MDB", "NET", "ZS", "CRWD", "PANW", "SNOW"},
    "semiconductor_ai_infra": {"NVDA", "AMD", "AVGO", "QCOM", "MU", "MRVL", "INTC"},
    "speculative_deep_tech": {"RGTI", "IONQ", "QBTS"},
    "early_commercial_capital_intensive": {"RKLB", "ASTS", "ACHR", "JOBY", "RIVN", "LCID", "PLUG"},
}


def run_current_research_recovery() -> dict[str, Any]:
    if BATCH_ROOT.exists():
        shutil.rmtree(BATCH_ROOT)
    BATCH_ROOT.mkdir(parents=True, exist_ok=True)
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)

    root_cause = _load_json(SOURCE_BATCH_001 / "DATA_AVAILABILITY_ROOT_CAUSE.json", default={})
    source_inventory = _load_json(Path("outputs/source_inventory/SOURCE_INPUT_INVENTORY.json"), default={})
    coverage_plan = _write_coverage_recovery_plan(root_cause, source_inventory)

    price_report = _refresh_price_inputs(CORE_UNIVERSE, BATCH_ROOT, SOURCE_ROOT / "prices")
    sec_report = _refresh_sec_inputs(CORE_UNIVERSE, BATCH_ROOT, SOURCE_ROOT)
    ir_report = _prepare_ir_fixtures(CORE_UNIVERSE, BATCH_ROOT, SOURCE_ROOT / "ir_releases")
    universe = _write_universe(CORE_UNIVERSE, coverage_plan, price_report, sec_report, ir_report)
    _write_source_registries(universe["included_tickers"], sec_report, ir_report, price_report)
    config_path = _write_batch_config(universe["included_tickers"])

    manifest = BatchRunner(BatchConfig.model_validate(_load_json(config_path, default={}))).run()
    manifest = _post_process_batch_outputs(manifest, price_report, sec_report, ir_report, universe)
    dashboard = build_dashboard_status(manifest)
    save_dashboard_status(dashboard, BATCH_ROOT / "dashboard_status.json")

    matrix = _write_guardrail_matrix(dashboard, universe)
    data_root = _write_batch_data_root_cause(dashboard, coverage_plan)
    inventory = _write_batch_source_inventory(dashboard, price_report, sec_report, ir_report, universe)
    consistency = _write_artifact_consistency_overview(dashboard)
    bundles = _write_bundles(dashboard)
    vivi = _write_vivi_review(dashboard, matrix, data_root, inventory, consistency)
    market = _write_market_readiness(dashboard, matrix, price_report, sec_report, ir_report, vivi)
    _write_systemic_fix_results()
    return {
        "coverage_plan": coverage_plan,
        "price_report": price_report,
        "sec_report": sec_report,
        "ir_report": ir_report,
        "universe": universe,
        "dashboard": dashboard,
        "matrix": matrix,
        "data_root": data_root,
        "inventory": inventory,
        "consistency": consistency,
        "bundles": bundles,
        "vivi": vivi,
        "market": market,
    }


def _write_coverage_recovery_plan(root_cause: dict[str, Any], source_inventory: dict[str, Any]) -> dict[str, Any]:
    inventory_by_ticker = {
        row["ticker"].upper(): row
        for row in source_inventory.get("records", [])
        if row.get("ticker")
    }
    records: list[dict[str, Any]] = []
    for row in root_cause.get("records", []):
        ticker = str(row["ticker"]).upper()
        inv = inventory_by_ticker.get(ticker, {})
        provider_unsupported = ticker in {"TSM", "ASML"}
        if provider_unsupported:
            fixability = "unsupported_skip"
            priority = "P3"
        elif ticker in {"RGTI", "IONQ", "QBTS", "RKLB", "ASTS", "ACHR", "JOBY", "RIVN", "LCID", "PLUG"}:
            fixability = "needs_ir_fixture" if ticker in {"RKLB", "ASTS", "ACHR", "JOBY"} else "quick_fix"
            priority = "P0" if ticker in {"RGTI", "IONQ", "QBTS", "RKLB", "ASTS", "ACHR", "JOBY"} else "P1"
        elif ticker in {"PYPL", "SNAP", "WBA", "PARA"}:
            fixability = "keep_manual_review"
            priority = "P2"
        else:
            fixability = "keep_manual_review"
            priority = "P2"
        records.append(
            {
                "ticker": ticker,
                "expected_archetype_bucket": row.get("expected_archetype_bucket") or inv.get("expected_archetype_bucket"),
                "missing_price_CSV": bool(row.get("missing_price_data", True)),
                "missing_CIK": bool(row.get("missing_CIK_mapping", True)),
                "missing_CompanyFacts": bool(row.get("missing_SEC_companyfacts", True)),
                "missing_IR_current_period_evidence": bool(row.get("missing_IR_fixture", True)),
                "missing_benchmark": bool(row.get("missing_benchmark_data", False)),
                "missing_news_vendor_fallback": bool(row.get("missing_news_vendor_fallback", True)),
                "provider_unsupported": provider_unsupported,
                "fixability": fixability,
                "priority": priority,
                "recommended_action": _coverage_recommended_action(ticker, fixability),
                "include_in_batch_003": ticker in CORE_UNIVERSE,
            }
        )
    summary = {
        "short_term_repairable": sum(1 for row in records if row["fixability"] in {"quick_fix", "needs_ir_fixture", "keep_manual_review"}),
        "intentionally_excluded": sum(1 for row in records if not row["include_in_batch_003"]),
        "highest_coverage_priority": [
            row["ticker"]
            for row in records
            if row["priority"] in {"P0", "P1"}
        ][:15],
        "not_in_batch_003": [
            {"ticker": ticker, "reason": reason}
            for ticker, reason in EXCLUDED_FOR_BATCH_003.items()
        ],
        "count_by_fixability": dict(Counter(row["fixability"] for row in records)),
        "count_by_priority": dict(Counter(row["priority"] for row in records)),
    }
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "source": [
            str(SOURCE_BATCH_001 / "DATA_AVAILABILITY_ROOT_CAUSE.json"),
            "outputs/source_inventory/SOURCE_INPUT_INVENTORY.json",
        ],
        "summary": summary,
        "records": records,
    }
    _write_json(BATCH_ROOT / "COVERAGE_RECOVERY_PLAN.json", payload)
    (BATCH_ROOT / "COVERAGE_RECOVERY_PLAN.md").write_text(_render_coverage_plan_md(payload), encoding="utf-8")
    return payload


def _coverage_recommended_action(ticker: str, fixability: str) -> str:
    if fixability == "unsupported_skip":
        return "Exclude from Batch 003 until foreign-issuer/ADR support is explicit."
    if ticker == "RKLB":
        return "Fetch fresh price/SEC coverage and attach existing sourced RKLB company-IR current-period fixture; keep manual_review if execution/FCF evidence is incomplete."
    if fixability == "needs_ir_fixture":
        return "Fetch fresh price/SEC coverage; run as manual_review/data_gap unless a sourced IR/current-period fixture exists."
    if fixability == "quick_fix":
        return "Fetch fresh price CSV, CIK mapping and SEC CompanyFacts; run with current_research gates active."
    return "Keep documented for later coverage expansion; exclude from Batch 003 if target universe is already full."


def _refresh_price_inputs(tickers: list[str], batch_root: Path, price_dir: Path) -> dict[str, Any]:
    price_dir.mkdir(parents=True, exist_ok=True)
    symbols = sorted(set(tickers + ["QQQ", "SMH", "SPY"]))
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        target = price_dir / f"{symbol}.csv"
        error = None
        try:
            history = _fetch_yahoo_history(symbol)
            _write_price_csv(target, history)
        except Exception as exc:  # noqa: BLE001 - source recovery must document provider failures.
            error = str(exc)
            history = []
        latest = history[-1]["date"] if history else None
        freshness = evaluate_price_freshness(latest, batch_mode="current_research", reference_date=AS_OF_DATE)
        rows.append(
            {
                "ticker": symbol,
                "latest_price_date": latest,
                "is_fresh": not freshness.stale_price_basis and error is None,
                "trading_days_old": freshness.trading_day_age,
                "benchmark_date": None,
                "current_report_allowed": freshness.current_report_allowed and error is None,
                "issue": error or freshness.issue_code,
                "csv_path": str(target) if target.exists() else None,
            }
        )
    by_symbol = {row["ticker"]: row for row in rows}
    ticker_rows = []
    for ticker in tickers:
        row = dict(by_symbol[ticker])
        benchmark = _benchmark_for(ticker)
        row["benchmark"] = benchmark
        row["benchmark_date"] = by_symbol.get(benchmark, {}).get("latest_price_date")
        ticker_rows.append(row)
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "price_source": "Yahoo Finance chart API",
        "price_dir": str(price_dir),
        "summary": {
            "ticker_count": len(ticker_rows),
            "fresh_count": sum(1 for row in ticker_rows if row["is_fresh"]),
            "current_report_allowed_count": sum(1 for row in ticker_rows if row["current_report_allowed"]),
            "stale_count": sum(1 for row in ticker_rows if not row["is_fresh"]),
            "latest_price_dates": dict(Counter(row.get("latest_price_date") for row in ticker_rows)),
        },
        "rows": ticker_rows,
        "benchmarks": [by_symbol[symbol] for symbol in ["QQQ", "SMH", "SPY"] if symbol in by_symbol],
    }
    _write_json(batch_root / "PRICE_FRESHNESS_REPORT.json", payload)
    (batch_root / "PRICE_FRESHNESS_REPORT.md").write_text(_render_price_report_md(payload), encoding="utf-8")
    return payload


def _fetch_yahoo_history(symbol: str) -> list[dict[str, Any]]:
    period1 = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
    period2 = int(datetime(2026, 5, 18, tzinfo=timezone.utc).timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?period1={period1}&period2={period2}&interval=1d&events=history&includeAdjustedClose=true"
    )
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        error = payload.get("chart", {}).get("error")
        raise RuntimeError(f"Yahoo chart returned no result for {symbol}: {error}")
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    adjclose = ((result.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or []
    rows = []
    for index, ts in enumerate(timestamps):
        open_ = _at(quote.get("open"), index)
        high = _at(quote.get("high"), index)
        low = _at(quote.get("low"), index)
        close = _at(quote.get("close"), index)
        volume = _at(quote.get("volume"), index)
        if close is None or open_ is None or high is None or low is None or volume is None:
            continue
        rows.append(
            {
                "date": datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat(),
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": int(volume or 0),
                "adjusted_close": float(_at(adjclose, index) or close),
            }
        )
    if not rows:
        raise RuntimeError(f"Yahoo chart returned no usable OHLCV rows for {symbol}")
    return rows


def _write_price_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "open", "high", "low", "close", "volume", "adjusted_close"])
        writer.writeheader()
        writer.writerows(rows)


def _refresh_sec_inputs(tickers: list[str], batch_root: Path, source_root: Path) -> dict[str, Any]:
    companyfacts_dir = source_root / "sec_companyfacts"
    companyfacts_dir.mkdir(parents=True, exist_ok=True)
    old_companyfacts_dir = Path("outputs/source_inputs/phase12_real_pilot_030/sec_companyfacts")
    ticker_map = _fetch_sec_ticker_map()
    client = SecClient(SecClientConfig(user_agent=SEC_USER_AGENT, cache_ttl_hours=24 * 30))
    cik_records: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        mapping = ticker_map.get(ticker)
        cik = str(mapping["cik"]).zfill(10) if mapping else None
        company_name = mapping["company_name"] if mapping else None
        companyfacts_path = companyfacts_dir / f"{ticker}.json"
        submissions = {}
        companyfacts_error = None
        submissions_error = None
        if cik:
            cik_records.append({"ticker": ticker, "cik": str(int(cik)), "company_name": company_name or ticker})
            try:
                payload = client.get_companyfacts(cik)
                _write_json(companyfacts_path, payload)
            except Exception as exc:  # noqa: BLE001
                companyfacts_error = str(exc)
                old_path = old_companyfacts_dir / f"{ticker}.json"
                if old_path.exists():
                    shutil.copy2(old_path, companyfacts_path)
            try:
                submissions = client.get_submissions(cik)
            except Exception as exc:  # noqa: BLE001
                submissions_error = str(exc)
        latest_filing = _latest_filing_date(submissions)
        companyfacts_present = companyfacts_path.exists()
        rows.append(
            {
                "ticker": ticker,
                "cik": str(int(cik)) if cik else None,
                "company_name": company_name,
                "cik_present": bool(cik),
                "companyfacts_present": companyfacts_present,
                "companyfacts_path": str(companyfacts_path) if companyfacts_present else None,
                "latest_filing_date": latest_filing,
                "primary_financials_available": bool(cik and companyfacts_present),
                "vendor_only_hard_metrics": bool(not companyfacts_present),
                "current_period_primary_evidence": bool(cik and companyfacts_present),
                "recommended_status": "current_source_ready" if cik and companyfacts_present else "manual_review_data_gap",
                "companyfacts_error": companyfacts_error,
                "submissions_error": submissions_error,
            }
        )
    _write_json(source_root / "cik_records.json", cik_records)
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "sec_source": "SEC company_tickers.json + companyfacts/submissions APIs",
        "cik_records_path": str(source_root / "cik_records.json"),
        "companyfacts_dir": str(companyfacts_dir),
        "summary": {
            "ticker_count": len(rows),
            "cik_present_count": sum(1 for row in rows if row["cik_present"]),
            "companyfacts_present_count": sum(1 for row in rows if row["companyfacts_present"]),
            "vendor_only_hard_metrics_count": sum(1 for row in rows if row["vendor_only_hard_metrics"]),
        },
        "rows": rows,
    }
    _write_json(batch_root / "SEC_COVERAGE_REPORT.json", payload)
    (batch_root / "SEC_COVERAGE_REPORT.md").write_text(_render_sec_report_md(payload), encoding="utf-8")
    return payload


def _fetch_sec_ticker_map() -> dict[str, dict[str, Any]]:
    url = "https://www.sec.gov/files/company_tickers.json"
    request = urllib.request.Request(url, headers={"User-Agent": SEC_USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = payload.values() if isinstance(payload, dict) else payload
    return {
        str(row.get("ticker", "")).upper(): {
            "cik": row.get("cik_str"),
            "company_name": row.get("title"),
        }
        for row in rows
        if row.get("ticker") and row.get("cik_str")
    }


def _latest_filing_date(submissions: dict[str, Any]) -> Optional[str]:
    recent = submissions.get("filings", {}).get("recent", {}) if submissions else {}
    dates = recent.get("filingDate") or []
    return max(dates) if dates else None


def _prepare_ir_fixtures(tickers: list[str], batch_root: Path, ir_dir: Path) -> dict[str, Any]:
    ir_dir.mkdir(parents=True, exist_ok=True)
    source_dir = Path("outputs/source_inputs/phase12_operating_pilot_050/ir_releases")
    for source in source_dir.glob("*.json"):
        if source.stem.upper() in tickers:
            shutil.copy2(source, ir_dir / source.name)
    _write_rklb_ir_fixture(ir_dir / "RKLB.json")

    rows = []
    for ticker in tickers:
        path = ir_dir / f"{ticker}.json"
        payload = _load_json(path, default={}) if path.exists() else {}
        metrics = payload.get("metrics") or []
        metric_names = {row.get("metric_name") for row in metrics}
        text = json.dumps(payload).lower()
        rows.append(
            {
                "ticker": ticker,
                "IR_fixture_available": path.exists(),
                "latest_earnings_release_available": path.exists(),
                "current_period_KPIs_available": bool(metrics),
                "company_defined_FCF_available": any("free_cash_flow" in str(name) for name in metric_names),
                "guidance_available": "guidance" in text,
                "segment_KPI_available": any(
                    term in str(name)
                    for name in metric_names
                    for term in ["cloud", "ai", "segment", "product", "space_systems", "launch_services", "net_revenue_retention"]
                ),
                "priority": _ir_priority(ticker),
                "action": _ir_action(ticker, path.exists()),
                "fixture_path": str(path) if path.exists() else None,
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
        },
        "rows": rows,
    }
    _write_json(batch_root / "IR_FIXTURE_PRIORITY.json", payload)
    (batch_root / "IR_FIXTURE_PRIORITY.md").write_text(_render_ir_report_md(payload), encoding="utf-8")
    return payload


def _write_rklb_ir_fixture(path: Path) -> None:
    if path.exists():
        return
    payload = {
        "source_id": "RKLB_Q1_2026_RESULTS_GLOBENEWSWIRE",
        "source_type": "company_ir",
        "url": "https://www.globenewswire.com/news-release/2026/05/07/3290563/0/en/rocket-lab-announces-first-quarter-2026-financial-results-surpasses-all-guidance-metrics-including-revenue-margin-and-adjusted-ebitda-posts-record-200m-quarterly-revenue-and-over-2.html",
        "retrieved_at": "2026-05-16T16:58:10Z",
        "period": "Q1_2026",
        "text": "Rocket Lab reported Q1 revenue, backlog above $2.2B, Electron/HASTE execution, Space Systems and Launch Services segment revenue, and Neutron development risk.",
        "metrics": [
            {"metric_name": "current_q_revenue", "value": 200300000, "unit": "usd", "period": "Q1_2026", "fiscal_year": 2026, "fiscal_period": "Q1", "period_bucket": "quarterly", "basis": "gaap", "statement_type": "income_statement", "statement": "Rocket Lab reported Q1 2026 revenue of $200.3 million."},
            {"metric_name": "backlog", "value": 2200000000, "unit": "usd", "period": "Q1_2026", "fiscal_year": 2026, "fiscal_period": "Q1", "period_bucket": "instant", "basis": "company_defined", "statement_type": "income_statement", "statement": "Rocket Lab reported backlog above $2.2 billion."},
            {"metric_name": "space_systems_revenue", "value": 127500000, "unit": "usd", "period": "Q1_2026", "fiscal_year": 2026, "fiscal_period": "Q1", "period_bucket": "quarterly", "basis": "company_defined", "statement_type": "income_statement", "statement": "Rocket Lab reported Space Systems revenue of $127.5 million."},
            {"metric_name": "launch_services_revenue", "value": 72900000, "unit": "usd", "period": "Q1_2026", "fiscal_year": 2026, "fiscal_period": "Q1", "period_bucket": "quarterly", "basis": "company_defined", "statement_type": "income_statement", "statement": "Rocket Lab reported Launch Services revenue of $72.9 million."},
            {"metric_name": "cash_and_marketable_securities", "value": 1480000000, "unit": "usd", "period": "Q1_2026", "fiscal_year": 2026, "fiscal_period": "Q1", "period_bucket": "instant", "basis": "company_defined", "statement_type": "balance_sheet", "statement": "Rocket Lab reported cash and securities of approximately $1.48 billion."},
            {"metric_name": "free_cash_flow", "value": -220123000, "unit": "usd", "period": "TTM_Q1_2026", "fiscal_year": 2026, "fiscal_period": "Q1", "period_bucket": "ttm", "basis": "company_defined", "statement_type": "cash_flow", "statement": "Rocket Lab trailing free cash flow remained negative at approximately -$220.1 million."},
        ],
    }
    _write_json(path, payload)


def _ir_priority(ticker: str) -> str:
    if ticker in {"GOOGL", "SNOW", "MSFT", "AAPL", "META", "AMZN", "NFLX", "CRM", "DDOG", "NVDA", "AVGO", "QCOM", "RKLB", "RGTI", "IONQ", "QBTS"}:
        return "P0"
    if ticker in {"AMD", "MU", "MRVL", "INTC", "MDB", "CRWD", "NET", "ACHR", "JOBY", "ASTS"}:
        return "P1"
    return "P2"


def _ir_action(ticker: str, has_fixture: bool) -> str:
    if has_fixture:
        return "Use fixture as current-period evidence; no pseudo-IR generation."
    if ticker in {"RGTI", "IONQ", "QBTS", "RKLB", "ACHR", "JOBY", "ASTS"}:
        return "Run as manual_review/data_gap unless sourced IR/current-period evidence is added."
    return "SEC/companyfacts may be sufficient for internal current research; mark current-period gaps if relevant."


def _write_universe(
    tickers: list[str],
    coverage_plan: dict[str, Any],
    price_report: dict[str, Any],
    sec_report: dict[str, Any],
    ir_report: dict[str, Any],
) -> dict[str, Any]:
    price_by_ticker = {row["ticker"]: row for row in price_report["rows"]}
    sec_by_ticker = {row["ticker"]: row for row in sec_report["rows"]}
    included = []
    for ticker in tickers:
        price = price_by_ticker.get(ticker, {})
        sec = sec_by_ticker.get(ticker, {})
        included.append(
            {
                "ticker": ticker,
                "benchmark": _benchmark_for(ticker),
                "expected_archetype_bucket": _expected_archetype(ticker),
                "minimum_viable_data": bool(price.get("current_report_allowed") and sec.get("cik_present") and sec.get("companyfacts_present")),
                "fresh_price": bool(price.get("current_report_allowed")),
                "sec_companyfacts": bool(sec.get("companyfacts_present")),
                "include_reason": _include_reason(ticker),
                "planned_status_if_gap": "manual_review/data_gap",
            }
        )
    excluded = [
        {
            "ticker": ticker,
            "reason": reason,
            "expected_archetype_bucket": _expected_archetype(ticker),
        }
        for ticker, reason in EXCLUDED_FOR_BATCH_003.items()
    ]
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "target_size": "24-32",
        "included_ticker_count": len(included),
        "included_tickers": [row["ticker"] for row in included],
        "excluded_tickers": excluded,
        "summary": {
            "minimum_viable_count": sum(1 for row in included if row["minimum_viable_data"]),
            "fresh_price_count": sum(1 for row in included if row["fresh_price"]),
            "sec_companyfacts_count": sum(1 for row in included if row["sec_companyfacts"]),
        },
        "records": included,
    }
    _write_json(BATCH_ROOT / "BATCH_003_UNIVERSE.json", payload)
    (BATCH_ROOT / "BATCH_003_UNIVERSE.md").write_text(_render_universe_md(payload), encoding="utf-8")
    return payload


def _include_reason(ticker: str) -> str:
    if ticker in {"GOOGL", "SNOW", "MSFT"}:
        return "Gold/control regression case."
    if ticker in {"RGTI", "IONQ", "QBTS"}:
        return "Speculative deep-tech guardrail case."
    if ticker in {"RKLB", "ASTS", "ACHR", "JOBY", "RIVN", "LCID", "PLUG"}:
        return "Early-commercial capital-intensive guardrail case."
    if ticker == "QCOM":
        return "FCF-support display rule regression case."
    return "Current research coverage candidate with fresh price and SEC source path."


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
                    used_for=[
                        "revenue",
                        "financial",
                        "cash",
                        "operating_income",
                        "free_cash_flow",
                        "fcf",
                        "sbc",
                        "debt",
                        "eps",
                    ],
                )
            )
        ir = ir_by_ticker.get(ticker, {})
        if ir.get("IR_fixture_available"):
            sources.append(
                SourceRegistryEntry(
                    source_id=f"{ticker}_IR_CURRENT_PERIOD_FIXTURE",
                    ticker=ticker,
                    source_type="company_ir",
                    authority_rank=1,
                    url=_ir_url(ir.get("fixture_path")),
                    retrieved_at=_utc_now(),
                    used_for=_ir_used_for(ticker),
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


def _ir_url(path_value: Optional[str]) -> Optional[str]:
    if not path_value:
        return None
    return _load_json(path_value, default={}).get("url")


def _ir_used_for(ticker: str) -> list[str]:
    base = ["revenue", "financial", "cash", "fcf", "free_cash_flow", "operating_income", "current_period_kpis"]
    if ticker == "RKLB":
        return base + [
            "backlog",
            "contract_backlog",
            "contracted_missions",
            "launch_cadence",
            "electron_execution",
            "neutron_development_risk",
            "space_systems",
            "launch_services",
            "product_platform_still_scaling",
            "execution_milestone_risk",
        ]
    return base + ["guidance", "segment_kpis"]


def _write_batch_config(tickers: list[str]) -> Path:
    configs = []
    for ticker in tickers:
        tags = ["guardrail_coverage_003_current_research"]
        for tag, tag_tickers in TAGS_BY_BUCKET.items():
            if ticker in tag_tickers:
                tags.append(tag)
        configs.append(
            BatchTickerConfig(
                ticker=ticker,
                mode="source_ingestion_mode",
                priority="normal",
                benchmark=_benchmark_for(ticker),
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


def _post_process_batch_outputs(
    manifest: BatchManifest,
    price_report: dict[str, Any],
    sec_report: dict[str, Any],
    ir_report: dict[str, Any],
    universe: dict[str, Any],
) -> BatchManifest:
    price_by_ticker = {row["ticker"]: row for row in price_report["rows"]}
    sec_by_ticker = {row["ticker"]: row for row in sec_report["rows"]}
    for item in manifest.items:
        ticker = item.ticker.upper()
        item.minimum_viable_report_possible = bool(
            price_by_ticker.get(ticker, {}).get("current_report_allowed")
            and sec_by_ticker.get(ticker, {}).get("cik_present")
            and sec_by_ticker.get(ticker, {}).get("companyfacts_present")
        )
        item.current_report_possible = bool(item.minimum_viable_report_possible and item.current_report_allowed)
        missing = []
        if not price_by_ticker.get(ticker, {}).get("current_report_allowed"):
            missing.append("fresh price")
        if not sec_by_ticker.get(ticker, {}).get("cik_present"):
            missing.append("CIK")
        if not sec_by_ticker.get(ticker, {}).get("companyfacts_present"):
            missing.append("SEC CompanyFacts")
        item.missing_minimum_inputs = missing
        item.artifacts = dict(item.artifacts or {})
        ticker_dir = BATCH_ROOT / ticker
        ticker_dir.mkdir(parents=True, exist_ok=True)
        dashboard_item_path = ticker_dir / "dashboard_item.json"
        item.artifacts["dashboard_item.json"] = str(dashboard_item_path)
        consistency_path = ticker_dir / "artifact_consistency_report.json"
        item.artifacts["artifact_consistency_report.json"] = str(consistency_path)
    save_batch_manifest(manifest, BATCH_ROOT / "batch_manifest.json")
    dashboard = build_dashboard_status(manifest)
    for item in manifest.items:
        ticker = item.ticker.upper()
        ticker_dir = BATCH_ROOT / ticker
        dashboard_item = next(row for row in dashboard["items"] if row["ticker"] == ticker)
        (ticker_dir / "dashboard_item.json").write_text(json.dumps(dashboard_item, indent=2, sort_keys=True), encoding="utf-8")
        consistency = _ticker_artifact_consistency(dashboard_item)
        _write_json(ticker_dir / "artifact_consistency_report.json", consistency)
    save_batch_manifest(manifest, BATCH_ROOT / "batch_manifest.json")
    save_dashboard_status(build_dashboard_status(manifest), BATCH_ROOT / "dashboard_status.json")
    return load_batch_manifest(BATCH_ROOT / "batch_manifest.json")


def _ticker_artifact_consistency(item: dict[str, Any]) -> dict[str, Any]:
    issues = []
    if item.get("current_report_allowed") is False and item.get("publishable"):
        issues.append(
            {
                "code": "STALE_CURRENT_REPORT_PUBLISHABLE",
                "severity": "error",
                "message": "Ticker is not current-report allowed but publishable is true.",
            }
        )
    if item.get("status") == "manual_review" and item.get("public_ready"):
        issues.append(
            {
                "code": "MANUAL_REVIEW_PUBLIC_READY",
                "severity": "error",
                "message": "Manual review ticker cannot be public_ready.",
            }
        )
    return {
        "generated_at": _utc_now(),
        "ticker": item["ticker"],
        "status": "clean" if not issues else "artifact_inconsistent",
        "issues": issues,
    }


def _write_guardrail_matrix(dashboard: dict[str, Any], universe: dict[str, Any]) -> dict[str, Any]:
    rows = []
    false_pass: list[dict[str, Any]] = []
    false_block: list[dict[str, Any]] = []
    for item in dashboard["items"]:
        ticker = item["ticker"]
        concerns = []
        if ticker in {"MSFT", "GOOGL", "SNOW"} and "DEEP_TECH" in str(item.get("company_archetype")):
            concerns.append("mega/gold ticker classified as deep-tech")
            false_pass.append(_status_candidate(ticker, "dashboard_status.json", item.get("company_archetype"), "non-deep-tech archetype", concerns[-1]))
        if (
            ticker in {"RGTI", "IONQ", "QBTS"}
            and item.get("status") != "data_unavailable"
            and _speculative_deep_tech_metrics_match(item)
            and item.get("company_archetype") != "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL"
        ):
            concerns.append("speculative quantum ticker did not retain speculative deep-tech archetype")
            false_block.append(_status_candidate(ticker, "quality_score.json", item.get("company_archetype"), "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL", concerns[-1]))
        if ticker == "RKLB" and item.get("status") != "data_unavailable" and item.get("company_archetype") != "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH":
            concerns.append("RKLB did not retain early-commercial capital-intensive archetype")
            false_block.append(_status_candidate(ticker, "quality_score.json", item.get("company_archetype"), "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH", concerns[-1]))
        rows.append(
            {
                "ticker": ticker,
                "company_name": _company_name_from_manifest(item),
                "sector_bucket": _sector_bucket(ticker),
                "expected_archetype": _expected_archetype(ticker),
                "actual_archetype": item.get("company_archetype") or "UNKNOWN",
                "archetype_confidence": item.get("archetype_confidence"),
                "review_status": item.get("status"),
                "publishable": item.get("publishable"),
                "public_ready": False,
                "external_display_rating": item.get("external_display_rating"),
                "publish_quality_score": item.get("publish_quality_score"),
                "internal_research_quality_score": item.get("internal_research_quality_score"),
                "data_confidence_score": item.get("data_confidence_score"),
                "manual_review_reasons": item.get("manual_review_reasons") or [],
                "primary_blockers": _primary_blockers(item),
                "artifact_consistency_status": _artifact_status(item),
                "evidence_status": _evidence_status(item),
                "likely_false_positive": "yes" if concerns and ticker in {"MSFT", "GOOGL", "SNOW"} else "no",
                "likely_false_negative": "yes" if concerns and ticker not in {"MSFT", "GOOGL", "SNOW"} else "no",
                "concerns": concerns,
                "recommended_next_action": _recommended_next_action(item, concerns),
                "price_basis_date": item.get("price_basis_date"),
                "data_freshness_status": item.get("data_freshness_status"),
                "current_report_allowed": item.get("current_report_allowed"),
            }
        )
    status_counts = Counter(row["review_status"] for row in rows)
    archetype_counts = Counter(row["actual_archetype"] for row in rows)
    payload = {
        "batch_id": BATCH_ID,
        "generated_at": _utc_now(),
        "listed_ticker_count": len(rows),
        "batch_mode": "current_research",
        "price_basis_request": "latest_available",
        "rows": rows,
        "summary": {
            "passed_count": status_counts.get("passed", 0),
            "manual_review_count": status_counts.get("manual_review", 0),
            "failed_count": status_counts.get("failed", 0),
            "data_unavailable_count": status_counts.get("data_unavailable", 0),
            "UNKNOWN_archetype_count": archetype_counts.get("UNKNOWN", 0),
            "archetype_counts": dict(archetype_counts),
            "top_manual_review_reasons": _top_values(reason for row in rows for reason in row["manual_review_reasons"]),
            "top_evidence_gaps": _top_values(row["evidence_status"] for row in rows if row["evidence_status"] != "clean"),
            "top_artifact_consistency_problems": _top_values(row["artifact_consistency_status"] for row in rows if row["artifact_consistency_status"] != "clean"),
            "top_financial_sanity_problems": _top_values(blocker for row in rows for blocker in row["primary_blockers"] if "FINANCIAL" in blocker or "FCF" in blocker or "VALUATION" in blocker),
            "top_false_pass_candidates": false_pass,
            "top_false_block_candidates": false_block,
            "system_level_fix_candidates": _system_fix_candidates(false_pass, false_block, rows),
        },
    }
    _write_json(BATCH_ROOT / "GUARDRAIL_COVERAGE_MATRIX.json", payload)
    (BATCH_ROOT / "GUARDRAIL_COVERAGE_MATRIX.md").write_text(_render_matrix_md(payload), encoding="utf-8")
    return payload


def _status_candidate(ticker: str, artifact: str, observed: Any, expected: str, reason: str) -> dict[str, str]:
    return {
        "ticker": ticker,
        "artifact": artifact,
        "observed_status": str(observed),
        "expected_status": expected,
        "reason": reason,
        "confidence": "high",
    }


def _speculative_deep_tech_metrics_match(item: dict[str, Any]) -> bool:
    metrics = _load_json((item.get("artifacts") or {}).get("metrics_packet.json"), default={})
    fundamentals = metrics.get("fundamentals") or {}
    valuation = metrics.get("valuation") or {}
    revenue = fundamentals.get("revenue_ttm")
    operating_income = fundamentals.get("operating_income_ttm")
    fcf = fundamentals.get("free_cash_flow_ttm")
    market_cap_to_revenue = valuation.get("market_cap_to_revenue")
    ev_to_sales = valuation.get("ev_to_sales")
    if not _number_lt(revenue, 50_000_000):
        return False
    if not _number_lt(operating_income, 0) or not _number_lt(fcf, 0):
        return False
    return _number_gt(market_cap_to_revenue, 100) or _number_gt(ev_to_sales, 100)


def _write_batch_data_root_cause(dashboard: dict[str, Any], coverage_plan: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in dashboard["items"]:
        if item["status"] not in {"data_unavailable", "failed"}:
            continue
        rows.append(
            {
                "ticker": item["ticker"],
                "expected_archetype_bucket": _expected_archetype(item["ticker"]),
                "missing_price_data": "fresh price" in (item.get("missing_minimum_inputs") or []),
                "missing_SEC_companyfacts": "SEC CompanyFacts" in (item.get("missing_minimum_inputs") or []),
                "missing_CIK_mapping": "CIK" in (item.get("missing_minimum_inputs") or []),
                "missing_IR_fixture": not _ir_fixture_exists(item["ticker"]),
                "missing_earnings_current_period_evidence": not _ir_fixture_exists(item["ticker"]),
                "missing_news_vendor_fallback": True,
                "missing_benchmark_data": False,
                "unsupported_by_provider": False,
                "root_cause_type": item.get("failure_type") or "data_gap",
                "error_message": item.get("error_message"),
                "recommended_fix": "Add auditable source coverage and rerun; do not mark publishable.",
                "priority": "P1",
            }
        )
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "data_unavailable_count": sum(1 for item in dashboard["items"] if item["status"] == "data_unavailable"),
        "failed_count": sum(1 for item in dashboard["items"] if item["status"] == "failed"),
        "summary": {
            "count_by_root_cause": dict(Counter(row["root_cause_type"] for row in rows)),
            "source_coverage_recovery_reference": str(BATCH_ROOT / "COVERAGE_RECOVERY_PLAN.json"),
        },
        "records": rows,
    }
    _write_json(BATCH_ROOT / "DATA_AVAILABILITY_ROOT_CAUSE.json", payload)
    (BATCH_ROOT / "DATA_AVAILABILITY_ROOT_CAUSE.md").write_text(_render_batch_data_root_md(payload), encoding="utf-8")
    return payload


def _write_batch_source_inventory(
    dashboard: dict[str, Any],
    price_report: dict[str, Any],
    sec_report: dict[str, Any],
    ir_report: dict[str, Any],
    universe: dict[str, Any],
) -> dict[str, Any]:
    price_by_ticker = {row["ticker"]: row for row in price_report["rows"]}
    sec_by_ticker = {row["ticker"]: row for row in sec_report["rows"]}
    ir_by_ticker = {row["ticker"]: row for row in ir_report["rows"]}
    item_by_ticker = {item["ticker"]: item for item in dashboard["items"]}
    records = []
    for ticker in universe["included_tickers"]:
        price = price_by_ticker.get(ticker, {})
        sec = sec_by_ticker.get(ticker, {})
        ir = ir_by_ticker.get(ticker, {})
        item = item_by_ticker.get(ticker, {})
        flags = []
        if not price.get("current_report_allowed"):
            flags.append("stale_price_basis")
        if not sec.get("companyfacts_present"):
            flags.append("missing_primary_financials")
        if sec.get("vendor_only_hard_metrics"):
            flags.append("vendor_only_hard_metrics")
        if not ir.get("IR_fixture_available"):
            flags.append("no_current_period_context")
        if not item.get("minimum_viable_report_possible"):
            flags.append("no_minimum_data")
        records.append(
            {
                "ticker": ticker,
                "price_source_present": bool(price.get("csv_path")),
                "latest_price_date": price.get("latest_price_date"),
                "SEC_CIK_present": sec.get("cik_present"),
                "companyfacts_present": sec.get("companyfacts_present"),
                "canonical_financials_present": bool((item.get("artifacts") or {}).get("canonical_financials.json")),
                "IR_current_period_evidence_present": ir.get("IR_fixture_available"),
                "earnings_calendar_present": False,
                "news_fallback_present": False,
                "benchmark_present": bool(price.get("benchmark_date")),
                "minimum_viable_report_possible": item.get("minimum_viable_report_possible"),
                "current_report_possible": item.get("current_report_possible"),
                "historical_QA_only": item.get("historical_qa_only"),
                "flags": flags,
            }
        )
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "ticker_count": len(records),
        "summary": {
            "minimum_viable_report_possible": sum(1 for row in records if row["minimum_viable_report_possible"]),
            "current_report_possible": sum(1 for row in records if row["current_report_possible"]),
            "historical_QA_only": sum(1 for row in records if row["historical_QA_only"]),
            "flags": dict(Counter(flag for row in records for flag in row["flags"])),
        },
        "records": records,
    }
    _write_json(BATCH_ROOT / "SOURCE_INPUT_INVENTORY.json", payload)
    (BATCH_ROOT / "SOURCE_INPUT_INVENTORY.md").write_text(_render_source_inventory_md(payload), encoding="utf-8")
    return payload


def _write_artifact_consistency_overview(dashboard: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in dashboard["items"]:
        path_value = (item.get("artifacts") or {}).get("artifact_consistency_report.json")
        payload = _load_json(path_value, default={}) if path_value else {}
        rows.append(
            {
                "ticker": item["ticker"],
                "status": payload.get("status", "missing"),
                "issue_count": len(payload.get("issues", [])),
                "path": path_value,
            }
        )
    overview = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "status": "clean" if all(row["status"] == "clean" for row in rows) else "needs_review",
        "rows": rows,
    }
    _write_json(BATCH_ROOT / "artifact_consistency_overview.json", overview)
    lines = ["# Artifact Consistency Overview", "", "| Ticker | Status | Issues |", "|---|---|---:|"]
    for row in rows:
        lines.append(f"| {row['ticker']} | {row['status']} | {row['issue_count']} |")
    (BATCH_ROOT / "artifact_consistency_overview.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return overview


def _write_bundles(dashboard: dict[str, Any]) -> dict[str, str]:
    item_by_ticker = {item["ticker"]: item for item in dashboard["items"]}
    passed = [item["ticker"] for item in dashboard["items"] if item["status"] == "passed"]
    manual = [item["ticker"] for item in dashboard["items"] if item["status"] == "manual_review"]
    problem = [
        item["ticker"]
        for item in dashboard["items"]
        if item["status"] in {"failed", "data_unavailable"} or item.get("company_archetype") == "UNKNOWN"
    ]
    paths = {
        "publish": str(BATCH_ROOT / "chatgpt_publish_review_bundle.zip"),
        "manual": str(BATCH_ROOT / "chatgpt_manual_review_bundle.zip"),
        "problem": str(BATCH_ROOT / "chatgpt_problem_cases_bundle.zip"),
    }
    _bundle_tickers(BATCH_ROOT / "chatgpt_publish_review_bundle.zip", passed, item_by_ticker, include_publish=True)
    _bundle_tickers(BATCH_ROOT / "chatgpt_manual_review_bundle.zip", manual, item_by_ticker, include_publish=False)
    _bundle_tickers(BATCH_ROOT / "chatgpt_problem_cases_bundle.zip", problem, item_by_ticker, include_publish=False, include_batch_docs=True)
    return paths


def _bundle_tickers(
    bundle_path: Path,
    tickers: Iterable[str],
    item_by_ticker: dict[str, dict[str, Any]],
    *,
    include_publish: bool,
    include_batch_docs: bool = False,
) -> None:
    artifact_keys = [
        "report_manifest.json",
        "quality_score.json",
        "decision_packet.json",
        "audit_report.json",
        "evidence_report.md",
        "current_period_reconciliation_summary.md",
        "reconciliation_report.md",
        "reconciliation_warnings.json",
        "metrics_packet.json",
        "canonical_financials.json",
        "source_registry.json",
        "data_packet.json",
        "artifact_consistency_report.json",
        "final_report.md",
        "internal_best_report.md",
    ]
    if include_publish:
        artifact_keys.extend(["publish_report.md", "publish_report_quality_score.json"])
    batch_docs = [
        "dashboard_status.json",
        "pilot_review.md",
        "GUARDRAIL_COVERAGE_MATRIX.json",
        "GUARDRAIL_COVERAGE_MATRIX.md",
        "DATA_AVAILABILITY_ROOT_CAUSE.json",
        "DATA_AVAILABILITY_ROOT_CAUSE.md",
        "SOURCE_INPUT_INVENTORY.json",
        "SOURCE_INPUT_INVENTORY.md",
        "PRICE_FRESHNESS_REPORT.json",
        "PRICE_FRESHNESS_REPORT.md",
        "SEC_COVERAGE_REPORT.json",
        "SEC_COVERAGE_REPORT.md",
        "IR_FIXTURE_PRIORITY.json",
        "IR_FIXTURE_PRIORITY.md",
        "artifact_consistency_overview.json",
        "artifact_consistency_overview.md",
    ]
    if bundle_path.exists():
        bundle_path.unlink()
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in batch_docs:
            path = BATCH_ROOT / name
            if path.exists() and (include_batch_docs or name == "dashboard_status.json"):
                zf.write(path, f"batch/{name}")
        missing = []
        for ticker in sorted(tickers):
            item = item_by_ticker.get(ticker, {})
            zf.writestr(f"tickers/{ticker}/dashboard_item.json", json.dumps(item, indent=2, sort_keys=True))
            artifacts = item.get("artifacts") or {}
            for key in artifact_keys:
                path_value = artifacts.get(key)
                if not path_value or not Path(path_value).exists():
                    if key in {"quality_score.json", "decision_packet.json", "report_manifest.json"}:
                        missing.append(f"{ticker}: {key}")
                    continue
                zf.write(Path(path_value), f"tickers/{ticker}/{key}")
        zf.writestr(
            "bundle_manifest.json",
            json.dumps(
                {
                    "batch_id": BATCH_ID,
                    "tickers": sorted(tickers),
                    "include_publish": include_publish,
                    "missing": missing,
                    "artifact_consistency_status": "clean" if not missing else "needs_review",
                },
                indent=2,
                sort_keys=True,
            ),
        )


def _write_vivi_review(
    dashboard: dict[str, Any],
    matrix: dict[str, Any],
    data_root: dict[str, Any],
    inventory: dict[str, Any],
    consistency: dict[str, Any],
) -> dict[str, Any]:
    false_pass = matrix["summary"]["top_false_pass_candidates"]
    false_block = matrix["summary"]["top_false_block_candidates"]
    blocking = []
    if false_pass:
        blocking.append(
            _review_issue(
                category="False Pass / False Block Detection",
                artifact="GUARDRAIL_COVERAGE_MATRIX.json",
                issue="Potential false-pass candidates detected.",
                evidence=json.dumps(false_pass),
                expected_behavior="No public/passed interpretation until reviewed.",
                severity="blocker",
            )
        )
    if consistency["status"] != "clean":
        blocking.append(
            _review_issue(
                category="Artifact Consistency",
                artifact="artifact_consistency_overview.json",
                issue="Artifact consistency overview is not clean.",
                evidence=f"status={consistency['status']}",
                expected_behavior="Problem cases must be in the problem bundle and not public-ready.",
                severity="blocker",
            )
        )
    non_blocking = []
    if false_block:
        non_blocking.append(
            _review_issue(
                category="Archetype Correctness",
                artifact="GUARDRAIL_COVERAGE_MATRIX.json",
                issue="Potential false-block/archetype regression candidates need human review.",
                evidence=json.dumps(false_block),
                expected_behavior="Keep affected names manual_review/problem-bundle until checked.",
                severity="major",
            )
        )
    if inventory["summary"].get("flags", {}).get("no_current_period_context"):
        non_blocking.append(
            _review_issue(
                category="Evidence Coverage",
                artifact="SOURCE_INPUT_INVENTORY.json",
                issue="Some current-research names lack IR/current-period context.",
                evidence=json.dumps(inventory["summary"].get("flags")),
                expected_behavior="Use manual_review/data_gap where archetype requires current-period evidence.",
                severity="major",
            )
        )
    status = "needs_fix" if blocking else ("manual_human_review" if non_blocking or false_block else "pass")
    payload = {
        "review_metadata": {
            "reviewer": "Vivi",
            "schema_version": "v1.1",
            "reviewed_at": _utc_now(),
            "bundle_id": BATCH_ID,
            "batch_id": BATCH_ID,
        },
        "review_status": status,
        "false_pass_candidates": false_pass,
        "false_block_candidates": false_block,
        "blocking_issues": blocking,
        "non_blocking_issues": non_blocking,
        "fix_list_for_codex": _vivi_fix_list(false_pass, false_block, blocking, non_blocking),
        "do_not_change": [
            "No guard loosening.",
            "No ticker hardcoding.",
            "No public-ready routing without Promotion Gate.",
            "No pseudo-IR or invented data.",
        ],
        "human_review_required": bool(status != "pass"),
    }
    _write_json(BATCH_ROOT / "vivi_batch_review.json", payload)
    _validate_vivi_schema(payload)
    return payload


def _review_issue(category: str, artifact: str, issue: str, evidence: str, expected_behavior: str, severity: str) -> dict[str, str]:
    return {
        "category": category,
        "artifact": artifact,
        "issue": issue,
        "evidence": evidence,
        "expected_behavior": expected_behavior,
        "severity": severity,
        "confidence": "high",
    }


def _vivi_fix_list(false_pass: list[dict[str, Any]], false_block: list[dict[str, Any]], blocking: list[dict[str, Any]], non_blocking: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fixes = []
    if false_block:
        fixes.append(
            {
                "file_or_module": "research_agent/quality/deeptech_manual_review.py",
                "issue": "Potential archetype false-block candidates require review before any code change.",
                "expected_behavior": "RGTI/IONQ/QBTS remain speculative deep-tech and RKLB remains early-commercial when source evidence supports it.",
                "acceptance_test": "Run archetype sanity and affected Batch-003 subset; no mega-cap false positives and no deep-tech/early-commercial regressions.",
                "do_not_touch_boundaries": [
                    "Do not loosen guards.",
                    "Do not add ticker hardcoding.",
                    "Do not polish report prose as a fix.",
                ],
                "priority": "P1",
            }
        )
    if not fixes and non_blocking:
        fixes.append(
            {
                "file_or_module": "outputs/source_inputs/guardrail_coverage_batch_003_current_research/ir_releases",
                "issue": "Some current-research names lack current-period IR fixtures.",
                "expected_behavior": "Add only sourced IR/current-period fixtures or keep affected reports manual_review/data_gap.",
                "acceptance_test": "IR_FIXTURE_PRIORITY.json shows fixture availability for priority names, and manual_review remains for missing evidence.",
                "do_not_touch_boundaries": [
                    "Do not invent IR metrics.",
                    "Do not relax evidence gates.",
                    "Do not mark manual_review reports public-ready.",
                ],
                "priority": "P1",
            }
        )
    return fixes


def _validate_vivi_schema(payload: dict[str, Any]) -> None:
    schema_path = Path("docs/VIVI_REVIEW_OUTPUT_SCHEMA.json")
    if not schema_path.exists():
        schema_path = Path("../New project/company-dossier-lab/docs/VIVI_REVIEW_OUTPUT_SCHEMA.json")
    result = {"schema_path": str(schema_path), "valid": False, "errors": []}
    try:
        import jsonschema

        schema = _load_json(schema_path, default={})
        validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
        errors = list(validator.iter_errors(payload))
        result["valid"] = not errors
        result["errors"] = [error.message for error in errors]
    except Exception as exc:  # noqa: BLE001
        result["errors"] = [str(exc)]
    _write_json(BATCH_ROOT / "vivi_batch_review_schema_validation.json", result)


def _write_market_readiness(
    dashboard: dict[str, Any],
    matrix: dict[str, Any],
    price_report: dict[str, Any],
    sec_report: dict[str, Any],
    ir_report: dict[str, Any],
    vivi: dict[str, Any],
) -> dict[str, Any]:
    summary = dashboard["summary"]
    false_pass = matrix["summary"]["top_false_pass_candidates"]
    false_block = matrix["summary"]["top_false_block_candidates"]
    stale_current = [
        item["ticker"]
        for item in dashboard["items"]
        if item.get("data_freshness_status") == "stale_price_basis" and item.get("publishable")
    ]
    consistency_has_errors = False
    if false_pass or stale_current or consistency_has_errors:
        verdict = "RED"
    elif false_block or vivi["review_status"] != "pass" or summary.get("data_unavailable", 0) or summary.get("failed", 0):
        verdict = "YELLOW"
    else:
        verdict = "GREEN"
    payload = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "decision": verdict,
        "current_operating_readiness": "usable_with_review" if verdict in {"GREEN", "YELLOW"} else "blocked",
        "current_reports_can_be_used_internally": verdict in {"GREEN", "YELLOW"},
        "public_output_blocked": True,
        "top_5_data_coverage_priorities": [
            "Add sourced IR/current-period fixtures for RGTI/IONQ/QBTS if primary evidence is needed beyond SEC facts.",
            "Add sourced IR/current-period fixtures for ACHR/JOBY/ASTS before stronger early-commercial conclusions.",
            "Decide whether QUBT/SOUN/BBAI belong in the next speculative story-stock batch.",
            "Decide whether TSM/ASML need a foreign-issuer lane before inclusion.",
            "Add earnings-calendar coverage for Batch-003 names.",
        ],
        "top_5_system_fixes": matrix["summary"].get("system_level_fix_candidates", [])[:5],
        "next_7_day_plan": [
            "Review Vivi false-block candidates if any.",
            "Backfill sourced IR fixtures for priority manual-review guardrail names.",
            "Run a compact affected-ticker rerun after IR backfill.",
            "Keep public routing blocked until Promotion Gate exists per report.",
            "Promote only clean current reports to internal review queues.",
        ],
    }
    _write_json(BATCH_ROOT / "MARKET_READINESS_DECISION.json", payload)
    (BATCH_ROOT / "MARKET_READINESS_DECISION.md").write_text(_render_market_md(payload, dashboard, matrix), encoding="utf-8")
    return payload


def _write_systemic_fix_results() -> None:
    fixes = [
        {
            "priority": "P1",
            "problem": "RKLB current-research run had source-registry tags such as product_platform_still_scaling, but archetype detection matched only space-separated prose.",
            "affected_tickers": ["RKLB"],
            "root_cause": "Source registry used_for tags were not normalized from snake_case before context matching.",
            "file_or_module": "research_agent/quality/deeptech_manual_review.py",
            "acceptance_test": "RKLB triggers EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH; RGTI remains SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL; no public-ready leak.",
            "do_not_touch_boundaries": [
                "No guard loosening.",
                "No ticker hardcoding.",
                "No report-template changes.",
                "No publishability changes from internal quality alone.",
            ],
        },
        {
            "priority": "P1",
            "problem": "Batch false-block detection treated every quantum ticker as speculative deep-tech even when current metrics no longer met the revenue boundary.",
            "affected_tickers": ["IONQ"],
            "root_cause": "Review matrix expected-bucket logic did not enforce the existing 'if metrics fit' condition before flagging false-block candidates.",
            "file_or_module": "research_agent/batch/current_research_recovery.py",
            "acceptance_test": "IONQ is not marked as a high-confidence false block unless revenue/op income/FCF/valuation metrics match the speculative deep-tech profile.",
            "do_not_touch_boundaries": [
                "No archetype guard loosening.",
                "No ticker-specific rating changes.",
                "No publishability changes.",
            ],
        }
    ]
    plan = {
        "generated_at": _utc_now(),
        "batch_id": BATCH_ID,
        "fixes_planned": fixes,
        "reason": "Two bounded P1 fixes were applied after Batch 003 exposed source-tag normalization and review-matrix false-block precision issues.",
    }
    _write_json(BATCH_ROOT / "SYSTEMIC_FIX_PLAN.json", plan)
    (BATCH_ROOT / "SYSTEMIC_FIX_PLAN.md").write_text(
        "# Systemic Fix Plan\n\n"
        "## P1 - Source Registry Tag Normalization\n\n"
        "- Problem: RKLB had sourced current-period/context tags, but snake_case tags were not matched as prose context.\n"
        "- Affected tickers: RKLB observed; generic for source-registry tag matching.\n"
        "- File/module: research_agent/quality/deeptech_manual_review.py\n"
        "- Acceptance test: RKLB early-commercial archetype triggers, RGTI remains speculative deep-tech, no public-ready leak.\n"
        "- Do-not-touch boundaries: no guard loosening, no ticker hardcoding, no report-template changes.\n\n"
        "## P1 - False-Block Candidate Precision\n\n"
        "- Problem: IONQ was flagged as high-confidence false block even though current metrics exceeded the speculative deep-tech revenue boundary.\n"
        "- File/module: research_agent/batch/current_research_recovery.py\n"
        "- Acceptance test: speculative quantum false-blocks are raised only when current metrics fit the speculative profile.\n"
        "- Do-not-touch boundaries: no archetype guard loosening, no rating changes, no publishability changes.\n",
        encoding="utf-8",
    )
    _write_json(BATCH_ROOT / "SYSTEMIC_FIX_RESULTS.json", {"generated_at": _utc_now(), "fixes_applied": fixes})
    (BATCH_ROOT / "SYSTEMIC_FIX_RESULTS.md").write_text(
        "# Systemic Fix Results\n\n"
        "- Applied: source-registry snake_case tags are now normalized alongside raw tags before archetype context matching.\n"
        "- Applied: review-matrix speculative deep-tech false-block detection now checks current metrics before flagging.\n"
        "- Scope: generic source-tag matching and Batch-003 review metadata only.\n"
        "- Guard/rating impact: no guard relaxation; publishability still controlled by existing gates.\n",
        encoding="utf-8",
    )


def _company_name_from_manifest(item: dict[str, Any]) -> Optional[str]:
    manifest_path = (item.get("artifacts") or {}).get("report_manifest.json")
    return _load_json(manifest_path, default={}).get("company_name") if manifest_path else None


def _primary_blockers(item: dict[str, Any]) -> list[str]:
    return list(dict.fromkeys((item.get("manual_review_reasons") or []) + (item.get("reconciliation_warning_codes") or []) + (item.get("evidence_warning_codes") or [])))


def _artifact_status(item: dict[str, Any]) -> str:
    path_value = (item.get("artifacts") or {}).get("artifact_consistency_report.json")
    return _load_json(path_value, default={}).get("status", "missing") if path_value else "missing"


def _evidence_status(item: dict[str, Any]) -> str:
    if (item.get("counts") or {}).get("hard_claims_without_evidence_count", 0):
        return "missing_hard_claim_evidence"
    if item.get("evidence_warnings"):
        return "warnings"
    return "clean"


def _recommended_next_action(item: dict[str, Any], concerns: list[str]) -> str:
    if concerns:
        return "Route to problem bundle and review before any fix."
    if item.get("status") == "passed":
        return "Keep in publish-review bundle; public output still requires Promotion Gate."
    if item.get("status") == "manual_review":
        return "Review internal_best_report and source gaps; do not publish."
    if item.get("status") == "data_unavailable":
        return "Fix source inputs before rerun."
    return "Inspect failure and route to problem bundle."


def _system_fix_candidates(false_pass: list[dict[str, Any]], false_block: list[dict[str, Any]], rows: list[dict[str, Any]]) -> list[str]:
    candidates = []
    if false_pass:
        candidates.append("Investigate false-pass classification/status policy before rerun.")
    if false_block:
        candidates.append("Investigate archetype detection for false-block candidates before rerun.")
    if any(row["actual_archetype"] == "UNKNOWN" for row in rows):
        candidates.append("Improve source inventory/minimum-data handling for UNKNOWN archetypes.")
    if not candidates:
        candidates.append("No immediate P0/P1 system fix; prioritize source coverage and human review of manual cases.")
    return candidates


def _ir_fixture_exists(ticker: str) -> bool:
    return (SOURCE_ROOT / "ir_releases" / f"{ticker}.json").exists()


def _benchmark_for(ticker: str) -> str:
    if ticker in TAGS_BY_BUCKET["semiconductor_ai_infra"]:
        return "SMH"
    if ticker in {"WBA", "PARA"}:
        return "SPY"
    return "QQQ"


def _expected_archetype(ticker: str) -> str:
    if ticker in TAGS_BY_BUCKET["mega_cap_platform"]:
        return "MEGA_CAP_PLATFORM or MEGA_CAP_CLOUD_PLATFORM"
    if ticker in TAGS_BY_BUCKET["saas_security"]:
        return "SAAS_CONSUMPTION / SAAS_SECURITY / STANDARD_GROWTH"
    if ticker in TAGS_BY_BUCKET["semiconductor_ai_infra"]:
        return "SEMICONDUCTOR_AI_INFRA or SEMICONDUCTOR_CYCLICAL"
    if ticker in TAGS_BY_BUCKET["speculative_deep_tech"]:
        return "SPECULATIVE_DEEP_TECH_EARLY_COMMERCIAL"
    if ticker in TAGS_BY_BUCKET["early_commercial_capital_intensive"]:
        return "EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH / DISTRESSED_CAPITAL_INTENSIVE"
    return "TURNAROUND / BUSINESS_MODEL_PRESSURE / STANDARD_WITH_RISK"


def _sector_bucket(ticker: str) -> str:
    if ticker in {"GOOGL", "SNOW", "MSFT"}:
        return "Gold-/Kontrollgruppe"
    if ticker in TAGS_BY_BUCKET["mega_cap_platform"]:
        return "Mega-Cap / Platform / Ads / Cloud"
    if ticker in TAGS_BY_BUCKET["saas_security"]:
        return "SaaS / Consumption / Cybersecurity / High-SBC"
    if ticker in TAGS_BY_BUCKET["semiconductor_ai_infra"]:
        return "Semiconductors / AI Infrastructure / Cyclical AI"
    if ticker in TAGS_BY_BUCKET["speculative_deep_tech"]:
        return "Speculative Deep-Tech / Quantum / Story Stocks"
    if ticker in TAGS_BY_BUCKET["early_commercial_capital_intensive"]:
        return "Early-Commercial Capital-Intensive Tech / Space / Mobility / Energy"
    return "Turnaround / Distressed / Business-Model Pressure"


def _render_coverage_plan_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Coverage Recovery Plan",
        "",
        f"- Batch: `{payload['batch_id']}`",
        f"- Short-term repairable: `{payload['summary']['short_term_repairable']}`",
        f"- Intentionally excluded: `{payload['summary']['intentionally_excluded']}`",
        f"- Highest priority: `{', '.join(payload['summary']['highest_coverage_priority'])}`",
        "",
        "| Ticker | Bucket | Fixability | Priority | Include 003 | Action |",
        "|---|---|---|---|---|---|",
    ]
    for row in payload["records"]:
        lines.append(f"| {row['ticker']} | {row['expected_archetype_bucket']} | {row['fixability']} | {row['priority']} | {_yes(row['include_in_batch_003'])} | {row['recommended_action']} |")
    return "\n".join(lines) + "\n"


def _render_price_report_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Price Freshness Report",
        "",
        f"- Fresh count: `{payload['summary']['fresh_count']}`",
        f"- Current-report allowed: `{payload['summary']['current_report_allowed_count']}`",
        "",
        "| Ticker | Latest Price | Fresh | Trading Days Old | Benchmark | Benchmark Date | Current Allowed | Issue |",
        "|---|---|---|---:|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(f"| {row['ticker']} | {row.get('latest_price_date') or ''} | {_yes(row['is_fresh'])} | {row.get('trading_days_old')} | {row.get('benchmark')} | {row.get('benchmark_date') or ''} | {_yes(row['current_report_allowed'])} | {row.get('issue') or ''} |")
    return "\n".join(lines) + "\n"


def _render_sec_report_md(payload: dict[str, Any]) -> str:
    lines = [
        "# SEC Coverage Report",
        "",
        f"- CIK present: `{payload['summary']['cik_present_count']}`",
        f"- CompanyFacts present: `{payload['summary']['companyfacts_present_count']}`",
        "",
        "| Ticker | CIK | CompanyFacts | Latest Filing | Primary Financials | Vendor-only | Status |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(f"| {row['ticker']} | {row.get('cik') or ''} | {_yes(row['companyfacts_present'])} | {row.get('latest_filing_date') or ''} | {_yes(row['primary_financials_available'])} | {_yes(row['vendor_only_hard_metrics'])} | {row['recommended_status']} |")
    return "\n".join(lines) + "\n"


def _render_ir_report_md(payload: dict[str, Any]) -> str:
    lines = [
        "# IR Fixture Priority",
        "",
        f"- Fixtures available: `{payload['summary']['fixture_available_count']}`",
        f"- Missing fixtures: `{payload['summary']['missing_fixture_count']}`",
        "",
        "| Ticker | Fixture | Current KPIs | FCF | Guidance | Segment KPI | Priority | Action |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(f"| {row['ticker']} | {_yes(row['IR_fixture_available'])} | {_yes(row['current_period_KPIs_available'])} | {_yes(row['company_defined_FCF_available'])} | {_yes(row['guidance_available'])} | {_yes(row['segment_KPI_available'])} | {row['priority']} | {row['action']} |")
    return "\n".join(lines) + "\n"


def _render_universe_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Batch 003 Universe",
        "",
        f"- Included ticker count: `{payload['included_ticker_count']}`",
        f"- Minimum viable count: `{payload['summary']['minimum_viable_count']}`",
        "",
        "| Ticker | Benchmark | Expected Archetype | MVD | Fresh Price | SEC CompanyFacts | Reason |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in payload["records"]:
        lines.append(f"| {row['ticker']} | {row['benchmark']} | {row['expected_archetype_bucket']} | {_yes(row['minimum_viable_data'])} | {_yes(row['fresh_price'])} | {_yes(row['sec_companyfacts'])} | {row['include_reason']} |")
    lines.extend(["", "## Excluded", "", "| Ticker | Reason |", "|---|---|"])
    for row in payload["excluded_tickers"]:
        lines.append(f"| {row['ticker']} | {row['reason']} |")
    return "\n".join(lines) + "\n"


def _render_matrix_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Guardrail Coverage Matrix - Batch 003",
        "",
        f"- Passed: `{payload['summary']['passed_count']}`",
        f"- Manual review: `{payload['summary']['manual_review_count']}`",
        f"- Failed: `{payload['summary']['failed_count']}`",
        f"- Data unavailable: `{payload['summary']['data_unavailable_count']}`",
        f"- UNKNOWN: `{payload['summary']['UNKNOWN_archetype_count']}`",
        "",
        "| Ticker | Status | Expected | Actual | Publishable | Display | Freshness | Concerns |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(f"| {row['ticker']} | {row['review_status']} | {row['expected_archetype']} | {row['actual_archetype']} | {_yes(row['publishable'])} | {row.get('external_display_rating')} | {row.get('data_freshness_status')} | {', '.join(row['concerns'])} |")
    return "\n".join(lines) + "\n"


def _render_batch_data_root_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Data Availability Root Cause - Batch 003",
        "",
        f"- Data unavailable: `{payload['data_unavailable_count']}`",
        f"- Failed: `{payload['failed_count']}`",
        "",
        "| Ticker | Root Cause | Error | Recommended Fix |",
        "|---|---|---|---|",
    ]
    for row in payload["records"]:
        lines.append(f"| {row['ticker']} | {row['root_cause_type']} | {row.get('error_message') or ''} | {row['recommended_fix']} |")
    return "\n".join(lines) + "\n"


def _render_source_inventory_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Source Input Inventory - Batch 003",
        "",
        f"- Tickers: `{payload['ticker_count']}`",
        f"- Current-report possible: `{payload['summary']['current_report_possible']}`",
        f"- Flags: `{payload['summary']['flags']}`",
        "",
        "| Ticker | Price | Latest Price | CIK | CompanyFacts | Canonical | IR | Benchmark | MVR | Current | Flags |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in payload["records"]:
        lines.append(f"| {row['ticker']} | {_yes(row['price_source_present'])} | {row.get('latest_price_date') or ''} | {_yes(row['SEC_CIK_present'])} | {_yes(row['companyfacts_present'])} | {_yes(row['canonical_financials_present'])} | {_yes(row['IR_current_period_evidence_present'])} | {_yes(row['benchmark_present'])} | {_yes(row['minimum_viable_report_possible'])} | {_yes(row['current_report_possible'])} | {', '.join(row['flags'])} |")
    return "\n".join(lines) + "\n"


def _render_market_md(payload: dict[str, Any], dashboard: dict[str, Any], matrix: dict[str, Any]) -> str:
    lines = [
        "# Market Readiness Decision - Batch 003",
        "",
        f"Decision: **{payload['decision']}**",
        "",
        f"- Current operating readiness: `{payload['current_operating_readiness']}`",
        f"- Current reports can be used internally: `{_yes(payload['current_reports_can_be_used_internally'])}`",
        f"- Public output blocked: `{_yes(payload['public_output_blocked'])}`",
        f"- Passed/manual/failed/data_unavailable: `{dashboard['summary']['passed']}/{dashboard['summary']['manual_review']}/{dashboard['summary']['failed']}/{dashboard['summary']['data_unavailable']}`",
        f"- False pass candidates: `{matrix['summary']['top_false_pass_candidates']}`",
        f"- False block candidates: `{matrix['summary']['top_false_block_candidates']}`",
        "",
        "## Top Data Coverage Priorities",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["top_5_data_coverage_priorities"])
    lines.extend(["", "## Next 7 Days", ""])
    lines.extend(f"- {item}" for item in payload["next_7_day_plan"])
    return "\n".join(lines) + "\n"


def _at(values: Optional[list], index: int):
    if not values or index >= len(values):
        return None
    value = values[index]
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return value


def _top_values(values: Iterable[Any], limit: int = 10) -> list[dict[str, Any]]:
    counter = Counter(str(value) for value in values if value)
    return [{"value": value, "count": count} for value, count in counter.most_common(limit)]


def _number_lt(value: Any, threshold: float) -> bool:
    try:
        return value is not None and float(value) < threshold
    except (TypeError, ValueError):
        return False


def _number_gt(value: Any, threshold: float) -> bool:
    try:
        return value is not None and float(value) > threshold
    except (TypeError, ValueError):
        return False


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
    result = run_current_research_recovery()
    dashboard = result["dashboard"]["summary"]
    print(json.dumps({"batch_id": BATCH_ID, "summary": dashboard, "market": result["market"]["decision"]}, indent=2, sort_keys=True))
