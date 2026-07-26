from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from research_agent.research_core.ingestion.source_registry import (
    SourceRegistry,
    SourceRegistryEntry,
    save_source_registry,
)
from research_agent.research_core.models.report_config import ReportConfig
from research_agent.run_pipeline import run_research_pipeline
from research_agent.sources.prices.massive_price_provider import MassivePriceProvider
from research_agent.sources.prices.price_provider_base import PriceProviderBase
from research_agent.sources.sec.sec_client import SecClient, SecClientConfig


class CurrentResearchError(RuntimeError):
    """Fail-closed current-ingestion error with an operator-actionable reason."""


class CurrentResearchRequest(BaseModel):
    ticker: str
    as_of_date: str
    sec_user_agent: str
    price_provider: str = "massive"
    price_api_key: Optional[str] = Field(default=None, repr=False)
    lookback_calendar_days: int = 550
    staging_root: str = ".runtime/current-research"
    output_root: str = "research_agent/data/outputs"
    ir_release_dir: Optional[str] = None
    earnings_calendar_path: Optional[str] = None

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        symbol = value.strip().upper()
        if not symbol or len(symbol) > 24:
            raise ValueError("ticker is missing or invalid")
        return symbol

    @field_validator("as_of_date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        return date.fromisoformat(value).isoformat()

    @field_validator("sec_user_agent")
    @classmethod
    def validate_sec_identity(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("SEC User-Agent must include a contact email")
        return value.strip()

    @field_validator("lookback_calendar_days")
    @classmethod
    def validate_lookback(cls, value: int) -> int:
        if value < 400:
            raise ValueError("lookback_calendar_days must be at least 400")
        return value


def run_current_research(
    request: CurrentResearchRequest,
    *,
    price_provider: Optional[PriceProviderBase] = None,
    sec_client: Optional[SecClient] = None,
) -> dict[str, Any]:
    """Acquire current inputs and run the sole deterministic Room16 pipeline.

    This function has no ticker/company branches. SEC coverage is one issuer
    adapter; unsupported issuers stop with a provider-gap message and require
    another official-registry adapter, never a company-specific exception.
    """

    symbol = request.ticker
    as_of = date.fromisoformat(request.as_of_date)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    staging_dir = (
        Path(request.staging_root).expanduser().resolve() / symbol / request.as_of_date
    )
    source_dir = staging_dir / "sources"
    price_dir = source_dir / "prices"
    companyfacts_dir = source_dir / "sec_companyfacts"
    packet_root = staging_dir / "packets"
    for path in (price_dir, companyfacts_dir, packet_root, Path(request.output_root)):
        path.mkdir(parents=True, exist_ok=True)

    sec = sec_client or SecClient(
        SecClientConfig(user_agent=request.sec_user_agent, cache_ttl_hours=24)
    )
    issuer = _resolve_sec_issuer(sec.get_company_tickers(), symbol)
    if issuer is None:
        raise CurrentResearchError(
            f"{symbol} is not present in the official SEC ticker map. "
            "A jurisdiction-specific official issuer adapter is required; "
            "Room16 will not substitute vendor fundamentals."
        )

    cik = str(issuer["cik"])
    company_name = str(issuer["company_name"])
    companyfacts = sec.get_companyfacts(cik)
    submissions = sec.get_submissions(cik)
    companyfacts_path = companyfacts_dir / f"{symbol}.json"
    _write_json(companyfacts_path, companyfacts)
    cik_records_path = source_dir / "cik_records.json"
    _write_json(
        cik_records_path,
        [{"ticker": symbol, "cik": cik, "company_name": company_name}],
    )

    provider = price_provider or _build_price_provider(request)
    start = (as_of - timedelta(days=request.lookback_calendar_days)).isoformat()
    prices = provider.get_history(symbol, start, request.as_of_date)
    price_csv_path = price_dir / f"{symbol}.csv"
    prices.to_csv(price_csv_path, index=False)

    source_type = str(
        getattr(provider, "source_type", "unknown_market_data_provider")
    )
    if source_type not in {"exchange_ohlcv", "trusted_market_data_vendor"}:
        raise CurrentResearchError(
            f"Price provider source type {source_type!r} is not authority-grade."
        )
    source_url = str(getattr(provider, "source_url", "") or "")
    price_source_id = f"{symbol}_{request.price_provider.upper()}_DAILY_OHLCV"
    registry_id = f"{symbol}_{request.as_of_date}"
    registry = SourceRegistry(
        registry_id=registry_id,
        sources=[
            SourceRegistryEntry(
                source_id=price_source_id,
                ticker=symbol,
                source_type=source_type,
                authority_rank=2,
                url=source_url or None,
                retrieved_at=retrieved_at,
                used_for=["price", "volume", "technical_indicators"],
                owner=request.price_provider,
                source_tier="market_authority",
                freshness_status="current_ingestion",
            )
        ],
    )
    registry_path = packet_root / f"{registry_id}_source_registry.json"
    save_source_registry(registry, registry_path)

    config = ReportConfig(
        ticker=symbol,
        as_of_date=request.as_of_date,
        source_mode="source_ingestion_mode",
        batch_mode="current_research",
        freshness_reference_date=request.as_of_date,
        output_dir=str(Path(request.output_root).expanduser().resolve()),
        packet_dir=str(packet_root),
        price_csv_dir=str(price_dir),
        price_start_date=start,
        price_source_id=price_source_id,
        price_source_type=source_type,
        price_source_url=source_url or None,
        price_retrieved_at=retrieved_at,
        cik_records_path=str(cik_records_path),
        sec_companyfacts_path=str(companyfacts_path),
        sec_user_agent=request.sec_user_agent,
        ir_release_dir=request.ir_release_dir,
        earnings_calendar_path=request.earnings_calendar_path,
    )
    run_research_pipeline(symbol, request.as_of_date, config)

    authority_dir = (
        Path(request.output_root).expanduser().resolve()
        / symbol
        / request.as_of_date
        / "authority_bundle"
    )
    manifest_path = authority_dir / "authority_manifest.json"
    if not manifest_path.exists():
        raise CurrentResearchError(
            "Deterministic pipeline completed without an authority manifest."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = {
        "status": "authority_ready",
        "ticker": symbol,
        "as_of_date": request.as_of_date,
        "company_name": company_name,
        "cik": cik,
        "latest_filing_date": _latest_filing_date(submissions),
        "price_provider": request.price_provider,
        "price_source_type": source_type,
        "price_row_count": int(len(prices)),
        "price_latest_date": str(prices.iloc[-1]["date"]),
        "authority_bundle": str(authority_dir),
        "authority_contract": manifest.get("contract_id"),
        "analysis_allowed": manifest.get("analysis_allowed"),
        "staging_dir": str(staging_dir),
    }
    _write_json(staging_dir / "current_ingestion_result.json", result)
    return result


def request_from_environment(ticker: str, as_of_date: str) -> CurrentResearchRequest:
    return CurrentResearchRequest(
        ticker=ticker,
        as_of_date=as_of_date,
        sec_user_agent=os.environ.get("ROOM16_SEC_USER_AGENT", ""),
        price_provider=os.environ.get("ROOM16_PRICE_PROVIDER", "massive"),
        price_api_key=(
            os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY")
        ),
        staging_root=os.environ.get(
            "ROOM16_CURRENT_RESEARCH_STAGING_ROOT", ".runtime/current-research"
        ),
        output_root=os.environ.get(
            "ROOM16_RESEARCH_AUTHORITY_ROOT", "research_agent/data/outputs"
        ),
    )


def _build_price_provider(request: CurrentResearchRequest) -> PriceProviderBase:
    if request.price_provider != "massive":
        raise CurrentResearchError(
            f"Unsupported price provider {request.price_provider!r}; "
            "configure an authority-grade provider adapter."
        )
    if not request.price_api_key:
        raise CurrentResearchError(
            "Massive/Polygon API key missing. Set MASSIVE_API_KEY or POLYGON_API_KEY."
        )
    return MassivePriceProvider(request.price_api_key)


def _resolve_sec_issuer(payload: dict[str, Any], ticker: str) -> Optional[dict[str, str]]:
    rows = payload.values() if isinstance(payload, dict) else payload
    for row in rows:
        if str(row.get("ticker") or "").strip().upper() != ticker:
            continue
        cik = row.get("cik_str")
        if cik is None:
            return None
        return {
            "cik": str(int(cik)),
            "company_name": str(row.get("title") or ticker),
        }
    return None


def _latest_filing_date(submissions: dict[str, Any]) -> Optional[str]:
    dates = (
        submissions.get("filings", {}).get("recent", {}).get("filingDate") or []
    )
    return max(dates) if dates else None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
