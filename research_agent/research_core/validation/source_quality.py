from __future__ import annotations

from datetime import datetime

from research_agent.research_core.ingestion.source_registry import (
    SOURCE_AUTHORITY,
    SourceRegistry,
    get_source_authority_rank,
)
from research_agent.research_core.models.data_packet import DataPacket


INSURER_OPERATING_METRICS = {
    "benefit_ratio",
    "combined_ratio",
    "loss_ratio",
    "medical_benefit_ratio",
    "member_months",
    "membership",
    "premiums_earned",
    "premiums_written",
}


def validate_news_price_causality(
    news_date: str,
    price_move_date: str,
    max_days: int = 1,
):
    nd = datetime.fromisoformat(news_date)
    pd = datetime.fromisoformat(price_move_date)

    delta_days = abs((pd - nd).days)

    if delta_days > max_days:
        return {
            "severity": "warning",
            "code": "WEAK_NEWS_PRICE_CAUSALITY",
            "message": (
                f"News date and price move date are {delta_days} days apart. "
                "Do not imply direct causality without additional evidence."
            ),
        }

    return None


def validate_source_authority(
    metric_name: str,
    source_type: str,
    authority_rank: int | None = None,
):
    rank = (
        authority_rank
        if authority_rank is not None
        else get_source_authority_rank(source_type)
    )

    if rank > 3:
        return {
            "severity": "warning",
            "code": "LOW_AUTHORITY_SOURCE_FOR_HARD_METRIC",
            "metric": metric_name,
            "source_type": source_type,
            "message": f"{metric_name} uses low-authority source {source_type}.",
        }

    return None


def validate_primary_financial_source(registry: SourceRegistry):
    has_primary = any(
        source.source_type in {"company_ir", "sec_filing"}
        for source in registry.sources
        for metric in source.used_for
        if metric not in {"price", "volume", "technical_indicators", "news"}
    )
    if not has_primary:
        return {
            "severity": "error",
            "code": "MISSING_PRIMARY_FINANCIAL_SOURCE",
            "message": "Hard financial metrics require at least one company IR or SEC filing source.",
        }
    return None


def validate_insurer_operating_kpi_coverage(
    data_packet: DataPacket,
    registry: SourceRegistry,
):
    business_context = " ".join(
        event.summary or ""
        for event in data_packet.news_coverage.material_events
        if event.event_type == "business_context"
    ).lower()
    identifies_insurer = any(
        phrase in business_context
        for phrase in (
            "health insurance product",
            "health care benefits segment",
            "insurance underwriting",
            "insurance business",
        )
    )
    if not identifies_insurer:
        return None
    primary_source_metrics = {
        metric
        for source in registry.sources
        if source.source_type in {"company_ir", "sec_filing"}
        for metric in source.used_for
    }
    if primary_source_metrics.intersection(INSURER_OPERATING_METRICS):
        return None
    return {
        "severity": "error",
        "code": "INSURER_OPERATING_KPI_CONTEXT_REQUIRED",
        "message": (
            "A material insurance business was identified, but no validated "
            "insurer operating KPI is integrated. Room16 requires a benefit/loss "
            "ratio, premiums, membership, or an equivalent primary-source KPI "
            "before starting the analysis."
        ),
    }
