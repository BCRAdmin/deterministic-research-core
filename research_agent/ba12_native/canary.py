"""Authorized WM/COST/ABT live-source canary execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from research_agent.ba12_live_source import (
    ExistingAdapterHarness,
    LiveCaptureExecutor,
    bridge_capture_set_to_ba3,
    verify_live_bridge,
)
from research_agent.semantic_compiler.source_frontend.planner import (
    build_compile_request,
    plan_source_acquisition,
)
from research_agent.sources.prices.nasdaq_price_provider import NasdaqPriceProvider
from research_agent.sources.sec.sec_client import SecClient, SecClientConfig

from .compiler import NativeCompileResult, build_native_bundle

COMPANIES = {
    "WM": {"cik": "823768", "name": "Waste Management, Inc.", "exchange": "NYSE", "exchange_code": "XNYS", "isin": "US94106L1098"},
    "COST": {"cik": "909832", "name": "Costco Wholesale Corporation", "exchange": "Nasdaq", "exchange_code": "XNAS", "isin": "US22160K1051"},
    "ABT": {"cik": "1800", "name": "Abbott Laboratories", "exchange": "NYSE", "exchange_code": "XNYS", "isin": "US0028241000"},
}


@dataclass(frozen=True)
class CanaryResult:
    ticker: str
    snapshot_sha256: str
    live_receipt_sha256s: tuple[str, ...]
    bridge_verification: dict[str, object]
    compile_result: NativeCompileResult


def run_live_canary(*, ticker: str, as_of_date: str, execution_root: Path, output_root: Path, sec_user_agent: str, research_commit: str, research_tree: str, monotonic_counter: int) -> CanaryResult:
    symbol = ticker.upper()
    company = COMPANIES[symbol]
    resolution = {"status": "supported", "runtimeReady": True, "inputKind": "ticker", "input": symbol, "ticker": symbol, "companyName": company["name"], "exchange": company["exchange"], "exchangeCode": company["exchange_code"], "jurisdiction": "US", "isin": company["isin"], "source": "ba12_operator_canary"}
    request = build_compile_request(resolution, as_of_date=as_of_date, allowed_provider_ids=("nasdaq", "sec"), available_configuration_ids=("ROOM16_SEC_USER_AGENT",), network_mode="live_acquisition")
    plan = plan_source_acquisition(request, price_provider_id="nasdaq")
    executor = LiveCaptureExecutor(execution_root)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    cutoff = datetime.combine(date.fromisoformat(as_of_date), datetime.max.time(), tzinfo=timezone.utc).replace(microsecond=0)
    authority_time = min(now, cutoff).isoformat().replace("+00:00", "Z")
    start = (date.fromisoformat(as_of_date) - timedelta(days=400)).isoformat()
    sec = SecClient(SecClientConfig(user_agent=sec_user_agent, use_cache=False))
    nasdaq = NasdaqPriceProvider()
    adapters = {
        "sec": ExistingAdapterHarness(provider_id="sec", adapter=sec, method_name="get_companyfacts", source_id=f"SEC_COMPANYFACTS_CIK{str(company['cik']).zfill(10)}", source_type="sec_filing", original_locator=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(company['cik']).zfill(10)}.json", final_locator=f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(company['cik']).zfill(10)}.json", raw_status="200", media_type="application/json", fetched_at_utc=authority_time, available_at_utc=authority_time, args=(company["cik"],)),
        "nasdaq": ExistingAdapterHarness(provider_id="nasdaq", adapter=nasdaq, method_name="get_history", source_id=f"NASDAQ_OHLCV_{symbol}", source_type="exchange_ohlcv", original_locator=f"https://www.nasdaq.com/market-activity/stocks/{symbol.lower()}/historical", final_locator=f"https://api.nasdaq.com/api/quote/{symbol}/historical", raw_status="200", media_type="application/json", fetched_at_utc=authority_time, available_at_utc=authority_time, args=(symbol, start, as_of_date)),
    }
    records = tuple(executor.capture(request=request, plan=plan, acquisition_id=item.acquisition_id, attempt_id=f"ba12.{symbol.lower()}.{item.provider_id}.1", adapter=adapters[item.provider_id]) for item in plan.acquisitions)
    snapshot_root = execution_root / "ba3_snapshot"
    bridge = bridge_capture_set_to_ba3(request=request, plan=plan, records=records, capture_store_root=executor.capture_store.root, snapshot_root=snapshot_root, staged_at_utc=authority_time)
    bridge_verification = verify_live_bridge(records=records, result=bridge, capture_store_root=executor.capture_store.root)
    compiled = build_native_bundle(snapshot=bridge.snapshot, snapshot_root=snapshot_root, output_root=output_root, research_commit=research_commit, research_tree=research_tree, monotonic_counter=monotonic_counter)
    return CanaryResult(symbol, bridge.snapshot.snapshot_sha256, tuple(sorted(item.receipt.receipt_sha256 for item in records)), bridge_verification, compiled)
