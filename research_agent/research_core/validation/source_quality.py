from __future__ import annotations

from datetime import datetime

from research_agent.research_core.ingestion.source_registry import (
    SOURCE_AUTHORITY,
    SourceRegistry,
    get_source_authority_rank,
)


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


def validate_source_authority(metric_name: str, source_type: str):
    rank = get_source_authority_rank(source_type)

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

