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
from research_agent.sources.bse.bse_provider import BseIssuerProvider
from research_agent.sources.prices.massive_price_provider import MassivePriceProvider
from research_agent.sources.prices.nasdaq_price_provider import NasdaqPriceProvider
from research_agent.sources.prices.price_provider_base import PriceProviderBase
from research_agent.sources.sec.sec_client import SecClient, SecClientConfig
from research_agent.sources.sec.sec_filing_risks import (
    build_sec_business_context_payload,
    build_sec_risk_evidence,
    save_sec_risk_evidence,
    select_sec_risk_filing_candidates,
)
from research_agent.sources.sec.sec_inline_facts import (
    build_sec_inline_fact_supplement_payload,
    merge_sec_inline_fact_supplement_payloads,
    save_sec_inline_fact_supplement,
)
from research_agent.sources.sec.sec_results_release import (
    build_sec_results_release_payload,
    select_sec_results_exhibit,
)
from research_agent.sources.sec.xbrl_concepts import US_GAAP_CONCEPTS


SEC_FINANCIAL_FORMS = {"10-K", "10-Q"}
SEC_RESULTS_ANNOUNCEMENT_FORM = "8-K"
SEC_RESULTS_ANNOUNCEMENT_ITEM = "2.02"
SEC_RESULTS_FILING_MATCH_WINDOW_DAYS = 14
SEC_FINANCIAL_INDUSTRY_SIC_RANGE = range(6000, 6800)
SEC_REIT_SIC_CODES = {6798}
SEC_SCHEDULED_AIRLINE_SIC_CODES = {4512}
SEC_CAPTIVE_FINANCE_ORIGINATION_CONCEPTS = {
    "IncreaseDecreaseInFinanceReceivables",
    "PaymentsToAcquireFinanceReceivables",
}
SEC_CAPTIVE_FINANCE_COLLECTION_CONCEPTS = {
    "ProceedsFromCollectionOfFinanceReceivables",
    "ProceedsFromSaleOfFinanceReceivables",
}
SEC_CAPTIVE_FINANCE_ACTIVITY_CONCEPTS = (
    SEC_CAPTIVE_FINANCE_ORIGINATION_CONCEPTS
    | SEC_CAPTIVE_FINANCE_COLLECTION_CONCEPTS
)
SEC_COMPANYFACTS_COVERAGE_METRICS = {
    "revenue",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "current_assets",
    "current_liabilities",
    "equity",
}


class CurrentResearchError(RuntimeError):
    """Fail-closed current-ingestion error with an operator-actionable reason."""


class CurrentResearchRequest(BaseModel):
    ticker: str
    as_of_date: str
    jurisdiction: Optional[str] = None
    isin: Optional[str] = None
    sec_user_agent: str = ""
    price_provider: str = "auto"
    price_api_key: Optional[str] = Field(default=None, repr=False)
    lookback_calendar_days: int = 550
    staging_root: str = ".runtime/current-research"
    output_root: str = "research_agent/data/outputs"
    ir_release_dir: Optional[str] = None
    earnings_calendar_path: Optional[str] = None
    official_news_dir: Optional[str] = None

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

    @field_validator("jurisdiction")
    @classmethod
    def normalize_jurisdiction(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        jurisdiction = value.strip().upper()
        if jurisdiction not in {"US", "HU"}:
            raise ValueError(f"unsupported jurisdiction hint: {jurisdiction}")
        return jurisdiction

    @field_validator("isin")
    @classmethod
    def normalize_isin(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        isin = value.strip().upper()
        if len(isin) != 12 or not isin[:2].isalpha() or not isin.isalnum():
            raise ValueError("ISIN hint is invalid")
        return isin

    @field_validator("sec_user_agent")
    @classmethod
    def validate_sec_identity(cls, value: str) -> str:
        if not value.strip():
            return ""
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
    bse_provider: Optional[BseIssuerProvider] = None,
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
    inline_facts_dir = source_dir / "sec_inline_facts"
    risk_factors_dir = source_dir / "sec_risk_factors"
    results_release_dir = source_dir / "sec_results_release"
    official_news_merge_dir = source_dir / "sec_official_news"
    packet_root = staging_dir / "packets"
    output_root = Path(request.output_root).expanduser().resolve()

    requested_jurisdiction = request.jurisdiction
    sec = sec_client
    if (
        sec is None
        and request.sec_user_agent
        and requested_jurisdiction != "HU"
    ):
        sec = SecClient(
            SecClientConfig(user_agent=request.sec_user_agent, cache_ttl_hours=24)
        )
    bse = bse_provider or BseIssuerProvider()
    issuer = None
    bse_issuer = None
    if requested_jurisdiction == "US":
        if sec is None:
            raise CurrentResearchError(
                f"{symbol} wurde als US-Emittent erkannt, aber die SEC-"
                "Kontaktkennung ROOM16_SEC_USER_AGENT fehlt oder ist ungültig."
            )
        issuer = _resolve_sec_issuer(sec.get_company_tickers(), symbol)
    elif requested_jurisdiction == "HU":
        bse_issuer = bse.resolve(symbol)
    else:
        issuer = _resolve_sec_issuer(sec.get_company_tickers(), symbol) if sec else None
        bse_issuer = bse.resolve(symbol)
        if issuer is not None and bse_issuer is not None:
            raise CurrentResearchError(
                f"{symbol} ist zwischen dem US-amerikanischen und dem ungarischen "
                "Emittentenregister mehrdeutig. Bitte Jurisdiktion oder ISIN "
                "eindeutig übergeben; Room16 errät das Wertpapier nicht."
            )
    if issuer is None and bse_issuer is None:
        if requested_jurisdiction:
            raise CurrentResearchError(
                f"{symbol} wurde der Jurisdiktion {requested_jurisdiction} "
                "zugeordnet, aber der zuständige offizielle Marktadapter konnte "
                "diese Identität nicht bestätigen. Room16 weicht nicht auf einen "
                "anderen Markt aus."
            )
        if sec is None:
            raise CurrentResearchError(
                f"{symbol} konnte nicht gegen das SEC-Emittentenregister geprüft "
                "werden, weil ROOM16_SEC_USER_AGENT fehlt oder ungültig ist; kein "
                "anderer aktivierter offizieller Marktadapter hat das Unternehmen "
                "erkannt. Vor einem neuen Versuch mit einem US-Emittenten muss die "
                "SEC-Kontaktkennung eingerichtet werden. Room16 ersetzt offizielle "
                "Fundamentaldaten nicht durch Händlerdaten."
            )
        raise CurrentResearchError(
            f"{symbol} ist über die eingerichteten offiziellen Marktadapter nicht "
            "verfügbar. Für SEC-Emittenten muss die SEC-Kontaktkennung eingerichtet "
            "sein; für andere Märkte wird ein passender offizieller Adapter benötigt. "
            "Room16 ersetzt offizielle Fundamentaldaten nicht durch Händlerdaten."
        )

    cik: Optional[str] = None
    companyfacts_path: Optional[Path] = None
    inline_facts_path: Optional[Path] = None
    inline_facts_payload: Optional[dict[str, Any]] = None
    risk_factors_path: Optional[Path] = None
    risk_source_status = "not_applicable"
    risk_filing_date: Optional[str] = None
    risk_factor_count = 0
    risk_filing_to_save = None
    risk_filings_to_save = []
    risk_evidence_to_save = []
    business_context_status = "not_available"
    business_context_filing_date: Optional[str] = None
    business_context_count = 0
    business_context_payload: Optional[dict[str, Any]] = None
    results_release_status = "not_applicable"
    results_release_filing_date: Optional[str] = None
    results_release_metric_count = 0
    results_release_payload: Optional[dict[str, Any]] = None
    results_release_path: Optional[Path] = None
    cik_records_path: Optional[Path] = None
    ir_release_dir: Optional[Path] = (
        Path(request.ir_release_dir).expanduser().resolve()
        if request.ir_release_dir
        else None
    )
    financial_source: Optional[SourceRegistryEntry] = None
    earnings_calendar_path = request.earnings_calendar_path
    official_news_dir = request.official_news_dir
    jurisdiction = "US"
    isin: Optional[str] = None
    companyfacts: Optional[dict[str, Any]] = None
    submissions: Optional[dict[str, Any]] = None
    latest_financial_filing: Optional[dict[str, str]] = None
    bse_financial_payload: Optional[dict[str, Any]] = None
    bse_news_payload: Optional[dict[str, Any]] = None
    bse_calendar_path: Optional[Path] = None
    bse_calendar_payload: Optional[dict[str, Any]] = None
    if issuer is not None:
        assert sec is not None
        cik = str(issuer["cik"])
        company_name = str(issuer["company_name"])
        companyfacts = sec.get_companyfacts(cik)
        submissions = sec.get_submissions(cik)
        _require_supported_sec_industry_profile(symbol, submissions)
        _require_supported_sec_reporting_profile(symbol, companyfacts)
        latest_financial_filing = _require_current_sec_financial_filing_coverage(
            symbol,
            request.as_of_date,
            submissions,
            companyfacts,
        )
        latest_results_filing = _latest_sec_results_announcement(
            submissions,
            request.as_of_date,
        )
        if _sec_results_release_is_current_candidate(
            latest_results_filing,
            latest_financial_filing,
        ):
            if latest_financial_filing is None or latest_results_filing is None:
                _raise_uncovered_sec_results(symbol, latest_results_filing)
            filing_period = _companyfacts_filing_period(
                companyfacts,
                latest_financial_filing["accession_number"],
                request.as_of_date,
            )
            if filing_period is None or filing_period["fiscal_period"] not in {
                "Q1",
                "Q2",
                "Q3",
            }:
                _raise_uncovered_sec_results(symbol, latest_results_filing)
            try:
                results_primary_html = sec.get_filing_html(
                    cik=cik,
                    accession_number=latest_results_filing["accession_number"],
                    primary_document=latest_results_filing["primary_document"],
                )
                results_document = select_sec_results_exhibit(results_primary_html)
                results_html = sec.get_filing_html(
                    cik=cik,
                    accession_number=latest_results_filing["accession_number"],
                    primary_document=results_document,
                )
                results_release_payload = build_sec_results_release_payload(
                    ticker=symbol,
                    cik=cik,
                    accession_number=latest_results_filing["accession_number"],
                    filing_date=latest_results_filing["filing_date"],
                    exhibit_document=results_document,
                    html=results_html,
                    expected_fiscal_year=int(filing_period["fiscal_year"]),
                    expected_fiscal_period=filing_period["fiscal_period"],
                    period_end_date=filing_period["end_date"],
                    retrieved_at=retrieved_at,
                )
            except (RuntimeError, ValueError) as exc:
                raise CurrentResearchError(
                    f"{symbol} hat mit dem 8-K vom "
                    f"{latest_results_filing['filing_date']} Ergebnisse nach SEC "
                    "Item 2.02 für den aktuellen Finanzzeitraum veröffentlicht. "
                    "Der offizielle Ergebnis-Anhang konnte nicht nach dem engen, "
                    f"strukturierten Room16-Vertrag integriert werden: {exc}. "
                    "Room16 startet keine angeblich vollständige Analyse."
                ) from exc
            results_release_path = results_release_dir / f"{symbol}.json"
            results_release_status = "available"
            results_release_filing_date = latest_results_filing["filing_date"]
            results_release_metric_count = len(
                results_release_payload.get("metrics") or []
            )
        elif latest_results_filing is not None:
            results_release_status = "superseded_by_later_financial_filing"
        _require_supported_sec_captive_finance_profile(
            symbol,
            request.as_of_date,
            submissions,
            companyfacts,
            max_age_days=request.lookback_calendar_days,
        )
        companyfacts_path = companyfacts_dir / f"{symbol}.json"
        cik_records_path = source_dir / "cik_records.json"
        risk_source_status = "no_extractable_risk_factors"
        filing_candidates = select_sec_risk_filing_candidates(
            submissions,
            cik=cik,
            as_of_date=request.as_of_date,
        )
        filing_html_by_accession: dict[str, str] = {}
        seen_risk_statements: set[str] = set()
        for filing in filing_candidates:
            try:
                filing_html = sec.get_filing_html(
                    cik=filing.cik,
                    accession_number=filing.accession_number,
                    primary_document=filing.primary_document,
                )
            except RuntimeError:
                risk_source_status = "filing_fetch_failed"
                continue
            filing_html_by_accession[filing.accession_number] = filing_html
            risk_evidence = build_sec_risk_evidence(
                ticker=symbol,
                filing=filing,
                html=filing_html,
                retrieved_at=retrieved_at,
            )
            if not risk_evidence:
                continue
            if risk_filing_to_save is None:
                risk_factors_path = risk_factors_dir / f"{symbol}.json"
                risk_filing_to_save = filing
                risk_filing_date = filing.filing_date
            risk_filings_to_save.append(filing)
            for item in risk_evidence:
                statement_key = " ".join(item.statement.lower().split())
                if statement_key in seen_risk_statements:
                    continue
                seen_risk_statements.add(statement_key)
                risk_evidence_to_save.append(item)
                if len(risk_evidence_to_save) == 30:
                    break
            risk_source_status = "available"
            risk_factor_count = len(risk_evidence_to_save)
            if risk_factor_count >= 4 or len(risk_evidence_to_save) == 30:
                break
        latest_financial_reference = next(
            (
                filing
                for filing in filing_candidates
                if latest_financial_filing is not None
                and filing.accession_number
                == latest_financial_filing["accession_number"]
            ),
            None,
        )
        if latest_financial_reference is not None:
            latest_financial_html = filing_html_by_accession.get(
                latest_financial_reference.accession_number
            )
            if latest_financial_html is not None:
                try:
                    inline_facts_payload = build_sec_inline_fact_supplement_payload(
                        ticker=symbol,
                        filing=latest_financial_reference,
                        html=latest_financial_html,
                        companyfacts=companyfacts,
                        retrieved_at=retrieved_at,
                    )
                except ValueError as exc:
                    raise CurrentResearchError(
                        f"{symbol} weist im aktuellen SEC-Bericht eine Inline-XBRL-"
                        "Struktur aus, die der enge Ergänzungsweg nicht sicher "
                        f"konsolidieren kann: {exc}"
                    ) from exc
                if inline_facts_payload is not None:
                    inline_facts_path = inline_facts_dir / f"{symbol}.json"
        annual_filing = next(
            (filing for filing in filing_candidates if filing.form == "10-K"),
            None,
        )
        if annual_filing is not None:
            annual_html = filing_html_by_accession.get(
                annual_filing.accession_number
            )
            if annual_html is None:
                try:
                    annual_html = sec.get_filing_html(
                        cik=annual_filing.cik,
                        accession_number=annual_filing.accession_number,
                        primary_document=annual_filing.primary_document,
                    )
                except RuntimeError:
                    business_context_status = "filing_fetch_failed"
            if annual_html is not None:
                if (
                    latest_financial_reference is not None
                    and annual_filing.accession_number
                    != latest_financial_reference.accession_number
                ):
                    annual_inline_payload = build_sec_inline_fact_supplement_payload(
                        ticker=symbol,
                        filing=annual_filing,
                        html=annual_html,
                        companyfacts=companyfacts,
                        retrieved_at=retrieved_at,
                        allowed_metrics={"capex"},
                    )
                    inline_facts_payload = merge_sec_inline_fact_supplement_payloads(
                        inline_facts_payload,
                        annual_inline_payload,
                    )
                    if inline_facts_payload is not None:
                        inline_facts_path = inline_facts_dir / f"{symbol}.json"
                business_context_payload = build_sec_business_context_payload(
                    ticker=symbol,
                    filing=annual_filing,
                    html=annual_html,
                    retrieved_at=retrieved_at,
                )
                business_context_count = len(
                    business_context_payload.get("events") or []
                )
                if business_context_count:
                    business_context_status = "available"
                    business_context_filing_date = annual_filing.filing_date
                else:
                    business_context_status = "no_extractable_business_context"
        latest_filing_date = _latest_filing_date(
            submissions, as_of_date=request.as_of_date
        )
        provider = price_provider or _build_price_provider(request)
        provider_name = str(
            getattr(provider, "provider_id", None)
            or ("massive" if isinstance(provider, MassivePriceProvider) else "market_data")
        )
    else:
        assert bse_issuer is not None
        if request.isin and request.isin != bse_issuer.isin:
            raise CurrentResearchError(
                f"{symbol} gehört laut offiziellem BSE-Register zur ISIN "
                f"{bse_issuer.isin}, nicht zu {request.isin}. Room16 setzt die "
                "Analyse mit einer widersprüchlichen Wertpapieridentität nicht fort."
            )
        jurisdiction = "HU"
        isin = bse_issuer.isin
        company_name = bse_issuer.company_name
        ir_release_dir = source_dir / "bse_financials"
        bse_financial_payload = bse.build_financial_payload(
            bse_issuer,
            as_of_date=request.as_of_date,
            retrieved_at=retrieved_at,
        )
        bse_news_dir = source_dir / "bse_news"
        bse_news_payload = bse.build_news_payload(
            bse_issuer,
            as_of_date=request.as_of_date,
            retrieved_at=retrieved_at,
        )
        official_news_dir = str(bse_news_dir)
        calendar_builder = getattr(bse, "build_earnings_calendar", None)
        bse_calendar = (
            calendar_builder(
                bse_issuer,
                as_of_date=request.as_of_date,
                retrieved_at=retrieved_at,
            )
            if callable(calendar_builder)
            else {"events": []}
        )
        if bse_calendar.get("events"):
            bse_calendar_path = source_dir / "bse_earnings_calendar.json"
            bse_calendar_payload = bse_calendar
            earnings_calendar_path = str(bse_calendar_path)
        latest_filing_date = _latest_metric_date(bse_financial_payload)
        provider = price_provider or bse
        provider_name = "bse"
        financial_source = SourceRegistryEntry(
            source_id=str(bse_financial_payload["source_id"]),
            ticker=symbol,
            source_type="company_ir",
            authority_rank=1,
            url=bse_issuer.profile_url,
            retrieved_at=retrieved_at,
            used_for=sorted(
                {
                    str(item["metric_name"])
                    for item in bse_financial_payload.get("metrics") or []
                    if item.get("metric_name")
                }
            ),
            owner="Budapest Stock Exchange / issuer submissions",
            source_tier="official_financial_authority",
            freshness_status="current_ingestion",
        )

    source_type = str(
        getattr(provider, "source_type", "unknown_market_data_provider")
    )
    if source_type not in {"exchange_ohlcv", "trusted_market_data_vendor"}:
        raise CurrentResearchError(
            f"Der Kursdatenanbieter meldet den Quellentyp {source_type!r}; dieser "
            "erfüllt den verbindlichen Quellenstandard nicht."
        )
    start = (as_of - timedelta(days=request.lookback_calendar_days)).isoformat()
    prices = provider.get_history(symbol, start, request.as_of_date)
    if results_release_payload is not None:
        prices = _bound_price_history_after_corporate_actions(
            prices,
            results_release_payload,
        )

    for path in (price_dir, packet_root, output_root):
        path.mkdir(parents=True, exist_ok=True)
    if issuer is not None:
        assert companyfacts is not None
        assert companyfacts_path is not None
        assert cik_records_path is not None
        assert cik is not None
        _write_json(companyfacts_path, companyfacts)
        _write_json(
            cik_records_path,
            [{"ticker": symbol, "cik": cik, "company_name": company_name}],
        )
        if risk_factors_path is not None:
            assert risk_filing_to_save is not None
            save_sec_risk_evidence(
                risk_factors_path,
                filing=risk_filing_to_save,
                evidence=risk_evidence_to_save,
                filings=risk_filings_to_save,
            )
        if results_release_path is not None and results_release_payload is not None:
            _write_json(results_release_path, results_release_payload)
        generated_news_payloads = [
            payload
            for payload in (business_context_payload, results_release_payload)
            if payload is not None
        ]
        if generated_news_payloads:
            external_news_payload = _load_official_news_payload(
                symbol,
                request.official_news_dir,
            )
            if external_news_payload is not None:
                generated_news_payloads.insert(0, external_news_payload)
            merged_news_payload = _merge_official_news_payloads(
                generated_news_payloads,
                retrieved_at=retrieved_at,
            )
            _write_json(
                official_news_merge_dir / f"{symbol}_news.json",
                merged_news_payload,
            )
            official_news_dir = str(official_news_merge_dir)
        if inline_facts_path is not None and inline_facts_payload is not None:
            save_sec_inline_fact_supplement(
                inline_facts_path,
                inline_facts_payload,
            )
    else:
        assert ir_release_dir is not None
        assert bse_financial_payload is not None
        assert bse_news_payload is not None
        _write_json(ir_release_dir / f"{symbol}.json", bse_financial_payload)
        bse_news_dir = source_dir / "bse_news"
        _write_json(bse_news_dir / f"{symbol}_news.json", bse_news_payload)
        if bse_calendar_path is not None:
            assert bse_calendar_payload is not None
            _write_json(bse_calendar_path, bse_calendar_payload)

    price_csv_path = price_dir / f"{symbol}.csv"
    prices.to_csv(price_csv_path, index=False)
    source_url = str(getattr(provider, "source_url", "") or "")
    price_source_id = (
        f"{symbol}_US_MARKET_DAILY_OHLCV"
        if provider_name == "nasdaq"
        else f"{symbol}_{provider_name.upper()}_DAILY_OHLCV"
    )
    registry_id = f"{symbol}_{request.as_of_date}"
    registry_sources = [
        SourceRegistryEntry(
            source_id=price_source_id,
            ticker=symbol,
            source_type=source_type,
            authority_rank=2,
            url=source_url or None,
            retrieved_at=retrieved_at,
            used_for=["price", "volume", "technical_indicators"],
            owner=provider_name,
            source_tier="market_authority",
            freshness_status="current_ingestion",
        )
    ]
    if financial_source is not None:
        registry_sources.append(financial_source)
    if results_release_payload is not None:
        registry_sources.append(
            SourceRegistryEntry(
                source_id=str(results_release_payload["source_id"]),
                ticker=symbol,
                source_type="sec_filing",
                authority_rank=1,
                url=str(results_release_payload["url"]),
                retrieved_at=retrieved_at,
                used_for=sorted(
                    {
                        str(item["metric_name"])
                        for item in results_release_payload.get("metrics") or []
                        if item.get("metric_name")
                    }
                ),
                owner="SEC / issuer-filed Item 2.02 exhibit",
                source_tier="official_financial_authority",
                freshness_status="current_ingestion",
            )
        )
    registry = SourceRegistry(
        registry_id=registry_id,
        sources=registry_sources,
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
        cik_records_path=str(cik_records_path) if cik_records_path else None,
        sec_companyfacts_path=str(companyfacts_path) if companyfacts_path else None,
        sec_inline_facts_path=str(inline_facts_path) if inline_facts_path else None,
        sec_risk_factors_path=str(risk_factors_path) if risk_factors_path else None,
        sec_user_agent=request.sec_user_agent or None,
        ir_release_dir=str(ir_release_dir) if ir_release_dir else None,
        sec_results_release_path=(
            str(results_release_path) if results_release_path else None
        ),
        earnings_calendar_path=earnings_calendar_path,
        official_news_dir=official_news_dir,
        price_currency=bse_issuer.currency if bse_issuer else "USD",
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
            "Der deterministische Research-Lauf endete ohne Authority-Manifest. "
            "Room16 erstellt daraus keinen Bericht."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    result = {
        "status": "authority_ready",
        "ticker": symbol,
        "as_of_date": request.as_of_date,
        "company_name": company_name,
        "cik": cik,
        "jurisdiction": jurisdiction,
        "isin": isin,
        "latest_filing_date": latest_filing_date,
        "latest_financial_filing_date": (
            latest_financial_filing.get("filing_date")
            if issuer is not None and latest_financial_filing is not None
            else latest_filing_date
        ),
        "risk_source_status": risk_source_status,
        "risk_filing_date": risk_filing_date,
        "risk_factor_count": risk_factor_count,
        "business_context_status": business_context_status,
        "business_context_filing_date": business_context_filing_date,
        "business_context_count": business_context_count,
        "results_release_status": results_release_status,
        "results_release_filing_date": results_release_filing_date,
        "results_release_metric_count": results_release_metric_count,
        "inline_financial_fact_count": len(
            (inline_facts_payload or {}).get("facts") or []
        ),
        "price_provider": provider_name,
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


def _bound_price_history_after_corporate_actions(prices, payload: dict[str, Any]):
    events = payload.get("events")
    events = events if isinstance(events, list) else []
    action_dates = sorted(
        {
            str(event.get("date") or "")
            for event in events
            if isinstance(event, dict)
            and event.get("event_type") == "corporate_action"
            and _is_valid_iso_date(str(event.get("date") or ""))
        }
    )
    if not action_dates or prices.empty or "date" not in prices.columns:
        return prices
    bounded = prices.copy()
    existing_status = str(
        bounded.iloc[-1].get("series_adjustment_status") or ""
    )
    action_count = len(action_dates)
    if existing_status == "corporate_action_adjusted":
        bounded["corporate_action_count"] = action_count
        return bounded
    boundary = action_dates[-1]
    bounded = bounded[bounded["date"].astype(str) >= boundary].copy()
    if bounded.empty:
        raise CurrentResearchError(
            "Der offizielle Ergebnisbericht nennt eine Kapitalmaßnahme, aber die "
            "Kursquelle enthält danach keine Beobachtung. Room16 berechnet keine "
            "technischen Signale über eine nicht vergleichbare Kursreihe."
        )
    bounded["corporate_action_count"] = action_count
    bounded["series_adjustment_status"] = "post_corporate_action_only"
    return bounded


def _is_valid_iso_date(value: str) -> bool:
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def request_from_environment(
    ticker: str,
    as_of_date: str,
    *,
    jurisdiction: Optional[str] = None,
    isin: Optional[str] = None,
) -> CurrentResearchRequest:
    return CurrentResearchRequest(
        ticker=ticker,
        as_of_date=as_of_date,
        jurisdiction=jurisdiction,
        isin=isin,
        sec_user_agent=os.environ.get("ROOM16_SEC_USER_AGENT", ""),
        price_provider=os.environ.get("ROOM16_PRICE_PROVIDER", "auto"),
        price_api_key=(
            os.environ.get("MASSIVE_API_KEY") or os.environ.get("POLYGON_API_KEY")
        ),
        staging_root=os.environ.get(
            "ROOM16_CURRENT_RESEARCH_STAGING_ROOT", ".runtime/current-research"
        ),
        output_root=os.environ.get(
            "ROOM16_RESEARCH_AUTHORITY_ROOT", "research_agent/data/outputs"
        ),
        official_news_dir=os.environ.get("ROOM16_OFFICIAL_NEWS_DIR") or None,
    )


def _require_supported_sec_reporting_profile(
    ticker: str,
    companyfacts: dict[str, Any],
) -> None:
    facts = companyfacts.get("facts")
    if not isinstance(facts, dict) or not facts:
        raise CurrentResearchError(
            f"{ticker} wurde als SEC-Emittent erkannt, aber die offiziellen "
            "CompanyFacts enthalten noch keine standardisierte Finanzhistorie. "
            "Room16 startet keine leere oder aus einem anderen Rechtsträger "
            "zusammengesetzte Analyse. Nach einer Umstrukturierung muss zuerst "
            "eine allgemeine, offiziell belegte Vorgänger-/Nachfolger-Kette "
            "integriert werden."
        )
    if facts.get("us-gaap"):
        forms = sorted(
            {
                str(row.get("form"))
                for record in facts["us-gaap"].values()
                if isinstance(record, dict)
                for unit_rows in (record.get("units") or {}).values()
                for row in unit_rows
                if isinstance(row, dict) and row.get("form")
            }
        )
        if not forms or set(forms).intersection(SEC_FINANCIAL_FORMS):
            return
        form_label = "/".join(forms)
        if set(forms).intersection({"20-F", "40-F", "6-K"}):
            raise CurrentResearchError(
                f"{ticker} wurde als SEC-Emittent erkannt und verwendet US-GAAP, "
                f"berichtet aber über {form_label} als ausländischer Emittent. "
                "Der vorhandene SEC-Finanzadapter unterstützt US-GAAP-Daten aus "
                "10-K und 10-Q. Bei 20-F/40-F/6-K müssen Berichts- und "
                "Preiswährung, Ordinary Shares, ADS-Verhältnis und Perioden "
                "separat belegt werden. Room16 startet keine scheinbar vollständige "
                "Analyse, bis ein allgemeiner SEC-FPI-Adapter diese Grundlagen "
                "unterstützt."
            )
        raise CurrentResearchError(
            f"{ticker} wurde als SEC-Emittent erkannt und verwendet US-GAAP, "
            f"aber die offiziellen CompanyFacts enthalten nur die nicht "
            f"unterstützten Filing-Formulare {form_label}. Der vorhandene "
            "SEC-Finanzadapter unterstützt US-GAAP-Daten aus 10-K und 10-Q; "
            "Room16 setzt keine schwächeren Ersatzdaten ein."
        )
    if facts.get("ifrs-full"):
        forms = sorted(
            {
                str(row.get("form"))
                for record in facts["ifrs-full"].values()
                if isinstance(record, dict)
                for unit_rows in (record.get("units") or {}).values()
                for row in unit_rows
                if isinstance(row, dict) and row.get("form")
            }
        )
        form_label = "/".join(forms) if forms else "20-F/6-K"
        raise CurrentResearchError(
            f"{ticker} wurde als SEC-Emittent erkannt, verwendet in den offiziellen "
            f"CompanyFacts aber die IFRS-Taxonomie mit {form_label}-Filings. Der "
            "vorhandene SEC-Finanzadapter unterstützt US-GAAP-Daten aus 10-K und "
            "10-Q. Room16 deutet IFRS-Konzepte nicht über US-GAAP-Zuordnungen um und "
            "setzt keine schwächeren Ersatzdaten ein. Vor einer Analyse dieses "
            "Wertpapiers wird ein allgemeiner SEC-IFRS-Adapter benötigt."
        )
    namespaces = ", ".join(sorted(str(namespace) for namespace in facts))
    raise CurrentResearchError(
        f"{ticker} wurde als SEC-Emittent erkannt, aber die offiziellen "
        f"CompanyFacts enthalten nur die nicht unterstützten Taxonomien "
        f"{namespaces}. Eine US-GAAP- oder IFRS-Finanzhistorie fehlt. Room16 "
        "startet keine leere oder aus einem anderen Rechtsträger zusammengesetzte "
        "Analyse. Nach einer Umstrukturierung muss zuerst eine allgemeine, "
        "offiziell belegte Vorgänger-/Nachfolger-Kette integriert werden."
    )


def _require_supported_sec_industry_profile(
    ticker: str,
    submissions: dict[str, Any],
) -> None:
    sic_text = str(submissions.get("sic") or "").strip()
    try:
        sic = int(sic_text)
    except ValueError:
        return
    description = str(submissions.get("sicDescription") or "Unternehmen").strip()
    if sic in SEC_SCHEDULED_AIRLINE_SIC_CODES:
        raise CurrentResearchError(
            f"{ticker} wurde als SEC-Emittent und als {description} (SIC {sic}) "
            "eindeutig erkannt. Das allgemeine Analyseprofil enthält noch keine "
            "belastbare Airline-Sicht auf Passagier- und sonstige Erlöse, Kapazität, "
            "Verkehr, Auslastung, Stückerlöse, Treibstoff, Flotte und Leasing. "
            "Konzernumsatz, Gewinn und klassische Verschuldungskennzahlen allein "
            "reichen für eine vollständige Fluggesellschaftsanalyse nicht aus. "
            "Room16 startet deshalb keine allgemeine Analyse. Vor einem neuen Lauf "
            "wird ein generisches Airline-Branchenprofil aus Primärquellen benötigt."
        )
    if sic not in SEC_FINANCIAL_INDUSTRY_SIC_RANGE:
        return
    if sic in SEC_REIT_SIC_CODES:
        raise CurrentResearchError(
            f"{ticker} wurde als SEC-Emittent und als {description} (SIC {sic}) "
            "eindeutig erkannt. Das vorhandene Analyseprofil ist für operative "
            "Unternehmen ausgelegt; bei REITs wären klassischer Free Cashflow, "
            "Enterprise Value und industrielle Verschuldungskennzahlen ohne "
            "Immobilienkontext fachlich irreführend. Room16 startet deshalb keine "
            "allgemeine Analyse. Vor einem neuen Lauf wird ein generisches "
            "REIT-Branchenprofil mit FFO/AFFO, immobiliengerechter Verschuldung, "
            "Auslastung, Mietlaufzeiten und Ausschüttungsdeckung benötigt."
        )
    raise CurrentResearchError(
        f"{ticker} wurde als SEC-Emittent und als {description} (SIC {sic}) "
        "eindeutig erkannt. Das vorhandene Analyseprofil ist für operative "
        "Unternehmen ausgelegt; bei Finanzunternehmen wären klassischer Free "
        "Cashflow, Enterprise Value und industrielle Verschuldungskennzahlen "
        "fachlich irreführend. Room16 startet deshalb keine allgemeine Analyse. "
        "Vor einem neuen Lauf wird ein generisches Finanzbranchenprofil mit "
        "bank-, versicherungs- oder investmentgerechten Kennzahlen benötigt."
    )


def _require_supported_sec_captive_finance_profile(
    ticker: str,
    as_of_date: str,
    submissions: dict[str, Any],
    companyfacts: dict[str, Any],
    *,
    max_age_days: int,
) -> None:
    as_of = date.fromisoformat(as_of_date)
    current_concepts: list[str] = []
    us_gaap = (companyfacts.get("facts") or {}).get("us-gaap") or {}
    for concept in sorted(SEC_CAPTIVE_FINANCE_ACTIVITY_CONCEPTS):
        record = us_gaap.get(concept)
        if not isinstance(record, dict):
            continue
        has_current_fact = False
        for rows in (record.get("units") or {}).values():
            for row in rows:
                if not isinstance(row, dict) or row.get("form") not in SEC_FINANCIAL_FORMS:
                    continue
                try:
                    end = date.fromisoformat(str(row.get("end") or ""))
                    filed = date.fromisoformat(str(row.get("filed") or ""))
                    value = float(row.get("val"))
                except (TypeError, ValueError):
                    continue
                age_days = (as_of - end).days
                if 0 <= age_days <= max_age_days and filed <= as_of and value != 0:
                    has_current_fact = True
                    break
            if has_current_fact:
                break
        if has_current_fact:
            current_concepts.append(concept)
    current_concept_set = set(current_concepts)
    if not (
        current_concept_set.intersection(
            SEC_CAPTIVE_FINANCE_ORIGINATION_CONCEPTS
        )
        and current_concept_set.intersection(
            SEC_CAPTIVE_FINANCE_COLLECTION_CONCEPTS
        )
    ):
        return
    sic_text = str(submissions.get("sic") or "").strip()
    description = str(
        submissions.get("sicDescription") or "operatives Unternehmen"
    ).strip()
    industry_label = (
        f"{description} (SIC {sic_text})" if sic_text else description
    )
    raise CurrentResearchError(
        f"{ticker} wurde als SEC-Emittent und als {industry_label} "
        "eindeutig erkannt. Die aktuellen SEC-Fakten weisen zugleich mehrere "
        "Cashflow-Arten für Finanzierungsforderungen aus; das spricht für eine "
        "wesentliche integrierte Finanzdienstleistung. Das vorhandene operative "
        "Analyseprofil würde Finanzierungsschulden, Forderungsfinanzierung und "
        "konsolidierten Cashflow mit dem operativen Kerngeschäft vermischen. Room16 "
        "startet deshalb keine allgemeine Analyse. Vor einem neuen Lauf wird ein "
        "generisches Captive-Finance-Profil benötigt, das Kerngeschäft und "
        "Finanzdienstleistung bei Ergebnis, Cashflow und Verschuldung trennt."
    )


def _build_price_provider(request: CurrentResearchRequest) -> PriceProviderBase:
    if request.price_provider not in {"auto", "massive", "nasdaq"}:
        raise CurrentResearchError(
            f"Der Kursdatenanbieter {request.price_provider!r} wird nicht "
            "unterstützt. Bitte einen Adapter einrichten, der den verbindlichen "
            "Quellenstandard erfüllt."
        )
    if request.price_provider == "nasdaq":
        return NasdaqPriceProvider()
    if request.price_provider == "auto" and not request.price_api_key:
        return NasdaqPriceProvider()
    if not request.price_api_key:
        raise CurrentResearchError(
            "Der API-Schlüssel für Massive/Polygon fehlt. Für diesen bewusst "
            "gewählten Kursdatenweg muss MASSIVE_API_KEY oder POLYGON_API_KEY "
            "eingerichtet werden."
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


def _latest_filing_date(
    submissions: dict[str, Any], *, as_of_date: Optional[str] = None
) -> Optional[str]:
    dates = (
        submissions.get("filings", {}).get("recent", {}).get("filingDate") or []
    )
    eligible = [
        str(filing_date)
        for filing_date in dates
        if filing_date and (as_of_date is None or str(filing_date) <= as_of_date)
    ]
    return max(eligible) if eligible else None


def _require_current_sec_financial_filing_coverage(
    ticker: str,
    as_of_date: str,
    submissions: dict[str, Any],
    companyfacts: dict[str, Any],
) -> Optional[dict[str, str]]:
    latest = _latest_sec_financial_filing(submissions, as_of_date)
    if latest is None:
        return None
    accession = latest["accession_number"]
    if accession in _mapped_companyfacts_accessions(companyfacts, as_of_date):
        return latest
    raise CurrentResearchError(
        f"{ticker} hat mit dem {latest['form']} vom {latest['filing_date']} einen "
        "neueren offiziellen SEC-Finanzbericht, dessen standardisierte "
        f"CompanyFacts für die Einreichung {accession} noch nicht verfügbar "
        "sind. Room16 startet keine Analyse mit dem älteren Quartal als "
        "angeblich aktuellem Finanzstand. Bitte den Lauf nach der SEC-"
        "Aktualisierung erneut starten."
    )


def _latest_sec_financial_filing(
    submissions: dict[str, Any], as_of_date: str
) -> Optional[dict[str, str]]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form") or []
    filing_dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    candidates = [
        {
            "form": str(form),
            "filing_date": str(filing_dates[index]),
            "accession_number": str(accessions[index]),
        }
        for index, form in enumerate(forms)
        if form in SEC_FINANCIAL_FORMS
        and index < len(filing_dates)
        and index < len(accessions)
        and filing_dates[index]
        and accessions[index]
        and str(filing_dates[index]) <= as_of_date
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (item["filing_date"], item["accession_number"]),
    )


def _latest_sec_results_announcement(
    submissions: dict[str, Any], as_of_date: str
) -> Optional[dict[str, str]]:
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form") or []
    filing_dates = recent.get("filingDate") or []
    accessions = recent.get("accessionNumber") or []
    primary_documents = recent.get("primaryDocument") or []
    items = recent.get("items") or []
    candidates = []
    for index, form in enumerate(forms):
        if (
            form != SEC_RESULTS_ANNOUNCEMENT_FORM
            or index >= len(filing_dates)
            or index >= len(accessions)
            or index >= len(items)
        ):
            continue
        filing_date = str(filing_dates[index] or "")
        accession = str(accessions[index] or "")
        filing_items = {
            item.strip()
            for item in str(items[index] or "").replace(" ", "").split(",")
            if item.strip()
        }
        if (
            filing_date
            and accession
            and filing_date <= as_of_date
            and SEC_RESULTS_ANNOUNCEMENT_ITEM in filing_items
        ):
            candidates.append(
                {
                    "form": str(form),
                    "filing_date": filing_date,
                    "accession_number": accession,
                    "primary_document": (
                        str(primary_documents[index])
                        if index < len(primary_documents)
                        else ""
                    ),
                }
            )
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (item["filing_date"], item["accession_number"]),
    )


def _mapped_companyfacts_accessions(
    companyfacts: dict[str, Any], as_of_date: str
) -> set[str]:
    mapped_concepts = {
        concept
        for metric_name in SEC_COMPANYFACTS_COVERAGE_METRICS
        for concept in US_GAAP_CONCEPTS.get(metric_name, [])
    }
    us_gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    return {
        str(row.get("accn"))
        for concept in mapped_concepts
        for row_set in ((us_gaap.get(concept) or {}).get("units") or {}).values()
        for row in row_set
        if isinstance(row, dict)
        and row.get("accn")
        and row.get("filed")
        and str(row.get("filed")) <= as_of_date
        and row.get("form") in SEC_FINANCIAL_FORMS
    }


def _latest_metric_date(payload: dict[str, Any]) -> Optional[str]:
    dates = [
        str(item.get("date") or item.get("end_date") or "")
        for item in payload.get("metrics") or []
        if item.get("date") or item.get("end_date")
    ]
    return max(dates) if dates else None


def _sec_results_release_is_current_candidate(
    results_filing: Optional[dict[str, str]],
    financial_filing: Optional[dict[str, str]],
) -> bool:
    if results_filing is None:
        return False
    if financial_filing is None:
        return True
    try:
        result_date = date.fromisoformat(results_filing["filing_date"])
        financial_date = date.fromisoformat(financial_filing["filing_date"])
    except (KeyError, ValueError):
        return True
    return (
        financial_date - result_date
    ).days <= SEC_RESULTS_FILING_MATCH_WINDOW_DAYS


def _companyfacts_filing_period(
    companyfacts: dict[str, Any],
    accession_number: str,
    as_of_date: str,
) -> Optional[dict[str, Any]]:
    mapped_concepts = {
        concept
        for metric_name in SEC_COMPANYFACTS_COVERAGE_METRICS
        for concept in US_GAAP_CONCEPTS.get(metric_name, [])
    }
    candidates: list[tuple[int, str, str]] = []
    us_gaap = companyfacts.get("facts", {}).get("us-gaap", {})
    for concept in mapped_concepts:
        for rows in ((us_gaap.get(concept) or {}).get("units") or {}).values():
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if str(row.get("accn") or "") != accession_number:
                    continue
                if str(row.get("filed") or "") > as_of_date:
                    continue
                fiscal_period = str(row.get("fp") or "").upper()
                end_date = str(row.get("end") or "")
                try:
                    fiscal_year = int(row.get("fy"))
                    date.fromisoformat(end_date)
                except (TypeError, ValueError):
                    continue
                if fiscal_period not in {"Q1", "Q2", "Q3", "FY"}:
                    continue
                candidates.append((fiscal_year, fiscal_period, end_date))
    if not candidates:
        return None
    counts: dict[tuple[int, str, str], int] = {}
    for candidate in candidates:
        counts[candidate] = counts.get(candidate, 0) + 1
    best_count = max(counts.values())
    best = sorted(
        (candidate for candidate, count in counts.items() if count == best_count),
        key=lambda candidate: candidate[2],
        reverse=True,
    )
    if len(best) > 1 and best[0][2] == best[1][2]:
        return None
    fiscal_year, fiscal_period, end_date = best[0]
    return {
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "end_date": end_date,
    }


def _raise_uncovered_sec_results(
    ticker: str,
    results_filing: Optional[dict[str, str]],
) -> None:
    filing_date = (
        results_filing.get("filing_date")
        if results_filing is not None
        else "unbekanntem Datum"
    )
    raise CurrentResearchError(
        f"{ticker} hat mit dem 8-K vom {filing_date} Ergebnisse nach SEC Item "
        "2.02 veröffentlicht, deren Finanzperiode noch nicht eindeutig durch "
        "einen standardisierten aktuellen 10-Q/10-K-CompanyFacts-Stand gedeckt "
        "ist. Room16 baut keine GAAP-Zahlen aus Pressemitteilungstabellen nach "
        "und startet keine angeblich vollständige Analyse."
    )


def _load_official_news_payload(
    ticker: str,
    news_dir: Optional[str],
) -> Optional[dict[str, Any]]:
    if not news_dir:
        return None
    path = Path(news_dir).expanduser().resolve() / f"{ticker.upper()}_news.json"
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {"coverage_status": "available", "events": payload}
    if not isinstance(payload, dict):
        raise CurrentResearchError(
            f"Die vorhandenen offiziellen News-Eingaben für {ticker} sind kein "
            "JSON-Objekt oder keine Ereignisliste."
        )
    return payload


def _merge_official_news_payloads(
    payloads: list[dict[str, Any]],
    *,
    retrieved_at: str,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    sources_checked: list[str] = []
    seen_events: set[tuple[str, str, str, str]] = set()
    window_starts: list[str] = []
    window_ends: list[str] = []
    for payload in payloads:
        if payload.get("window_start"):
            window_starts.append(str(payload["window_start"]))
        if payload.get("window_end"):
            window_ends.append(str(payload["window_end"]))
        sources_checked.extend(
            str(source)
            for source in payload.get("sources_checked") or []
            if source
        )
        for event in payload.get("events") or []:
            if not isinstance(event, dict):
                continue
            key = (
                str(event.get("source_id") or ""),
                str(event.get("date") or ""),
                str(event.get("event_type") or ""),
                str(event.get("summary") or event.get("headline") or ""),
            )
            if key in seen_events:
                continue
            seen_events.add(key)
            events.append(event)
    return {
        "coverage_status": "available" if payloads else "unavailable",
        "checked_at": retrieved_at,
        "window_start": min(window_starts) if window_starts else None,
        "window_end": max(window_ends) if window_ends else None,
        "sources_checked": list(dict.fromkeys(sources_checked)),
        "events": events,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
