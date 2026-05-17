from __future__ import annotations

from typing import Iterable, Optional

from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationIssue, ValidationReport
from research_agent.research_core.validation.data_quality import (
    validate_data_packet,
    validate_indicator_date,
)
from research_agent.research_core.validation.metric_consistency import (
    validate_forward_eps_vs_guidance,
)
from research_agent.research_core.validation.rating_consistency import validate_rating_vs_actions
from research_agent.research_core.validation.source_quality import (
    validate_primary_financial_source,
    validate_source_authority,
)
from research_agent.research_core.validation.trading_logic import validate_trade_levels


def run_all_validations(
    data_packet: DataPacket,
    metrics_packet: MetricsPacket,
    source_registry: Optional[SourceRegistry] = None,
    trade_setups: Optional[Iterable[dict]] = None,
    rating: Optional[str] = None,
    actions: Optional[list[str]] = None,
) -> ValidationReport:
    raw_issues: list[dict] = []
    raw_issues.extend(validate_data_packet(data_packet))

    indicator_issue = validate_indicator_date(
        data_packet.price_basis.date,
        metrics_packet.technical.indicator_date,
    )
    if indicator_issue:
        raw_issues.append(indicator_issue)

    if data_packet.forward_eps and data_packet.company_guidance_eps:
        if (
            data_packet.forward_eps.value is not None
            and data_packet.company_guidance_eps.low is not None
            and data_packet.company_guidance_eps.high is not None
        ):
            issue = validate_forward_eps_vs_guidance(
                data_packet.forward_eps.value,
                data_packet.company_guidance_eps.low,
                data_packet.company_guidance_eps.high,
            )
            if issue:
                raw_issues.append(issue)

    if source_registry is None:
        raw_issues.append(
            {
                "severity": "error",
                "code": "MISSING_PRIMARY_FINANCIAL_SOURCE",
                "message": "Source registry with primary financial sources is required before report generation.",
            }
        )
    else:
        primary_issue = validate_primary_financial_source(source_registry)
        if primary_issue:
            raw_issues.append(primary_issue)
        for source in source_registry.sources:
            for metric_name in source.used_for:
                if metric_name not in {"price", "volume", "technical_indicators", "news"}:
                    issue = validate_source_authority(metric_name, source.source_type)
                    if issue:
                        raw_issues.append(issue)

    for trade_setup in trade_setups or []:
        raw_issues.extend(validate_trade_levels(**trade_setup))

    if rating is not None and actions:
        issue = validate_rating_vs_actions(rating, actions)
        if issue:
            raw_issues.append(issue)

    return ValidationReport.from_issues(
        ticker=data_packet.ticker,
        as_of_date=data_packet.as_of_date,
        issues=[_to_validation_issue(issue) for issue in raw_issues],
    )


def _to_validation_issue(issue: dict) -> ValidationIssue:
    allowed = {
        "severity": issue.get("severity"),
        "code": issue.get("code"),
        "message": issue.get("message", ""),
        "metric": issue.get("metric"),
        "computed": issue.get("computed"),
        "reported": issue.get("reported"),
    }
    return ValidationIssue(**allowed)
