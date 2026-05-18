from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Optional, Union

from research_agent.audit.audit_report import AuditIssue, AuditReport, ExtractedNumericClaim
from research_agent.audit.claim_mapper import map_claim_to_metric
from research_agent.audit.markdown_numeric_extractor import extract_numeric_claims
from research_agent.audit.rating_action_extractor import (
    extract_action_lines,
    extract_final_rating,
    infer_report_action_class,
)
from research_agent.decision.decision_packet import DecisionPacket
from research_agent.decision.rating_permission import extract_rating_from_text
from research_agent.evidence.evidence_ledger import EvidenceLedger, load_evidence_ledger
from research_agent.evidence.evidence_validator import validate_metric_evidence, validate_vendor_not_primary
from research_agent.reconciliation.canonical_financials import CanonicalFinancials
from research_agent.research_core.ingestion.source_registry import SourceRegistry
from research_agent.research_core.models.metrics_packet import MetricsPacket
from research_agent.research_core.models.validation_report import ValidationReport
from research_agent.quality.quality_report import QualityReport
from research_agent.quality.deeptech_manual_review import CompanyArchetype, assess_speculative_deep_tech_manual_review
from research_agent.research_core.validation.trading_logic import validate_trade_levels


CAUSALITY_RE = re.compile(
    r"(?:because of|due to|caused by|triggered by|aufgrund|wegen|führte zu|fuehrte zu|ausgelöst durch|ausgeloest durch)",
    re.IGNORECASE,
)
PRICE_NEWS_RE = re.compile(r"(?:news|nachricht|meldung|irland|kurs|price|selloff|rückgang|rueckgang)", re.IGNORECASE)
NO_NEWS_RE = re.compile(
    r"(?:no news found|no relevant news|no company-specific news found|keine news|keine relevanten nachrichten|keine unternehmensspezifischen nachrichten)",
    re.IGNORECASE,
)
HARD_METRIC_RE = re.compile(
    r"(?:fcf|free cash|cashflow|margin|marge|sbc|revenue|umsatz|kgv|p/e|sma|debt|cash|eps)",
    re.IGNORECASE,
)
GUIDANCE_CLAIM_RE = re.compile(r"\b(?:guidance|outlook|guided|expects|erwartet|prognose)\b", re.IGNORECASE)
GUIDANCE_UNAVAILABLE_RE = re.compile(
    r"(?:guidance unavailable|company guidance unavailable|missing company guidance|no company guidance|metric unavailable)",
    re.IGNORECASE,
)
EARNINGS_EVENT_RISK_RE = re.compile(
    r"(?:earnings event risk|event risk|earnings risk|earnings within|within 10 trading days|earnings-date risk|terminrisiko)",
    re.IGNORECASE,
)
EARNINGS_UNAVAILABLE_RE = re.compile(
    r"(?:earnings date unavailable|next earnings date unavailable|unconfirmed|metric unavailable)",
    re.IGNORECASE,
)


def audit_markdown_report(
    markdown: str,
    metrics_packet: MetricsPacket,
    validation_report: Optional[ValidationReport] = None,
    source_registry: Optional[SourceRegistry] = None,
    decision_packet: Optional[DecisionPacket] = None,
    evidence_ledger: Optional[EvidenceLedger] = None,
    canonical_financials: Optional[CanonicalFinancials] = None,
    reconciliation_warnings: Optional[list[dict]] = None,
    quality_report: Optional[QualityReport] = None,
    ticker: Optional[str] = None,
) -> AuditReport:
    claims = extract_numeric_claims(markdown)
    issues: list[AuditIssue] = []
    deeptech_assessment = assess_speculative_deep_tech_manual_review(
        markdown=markdown,
        metrics_packet=metrics_packet,
        source_registry=source_registry,
    )
    issues.extend(_lint_numeric_claims(claims, metrics_packet, evidence_ledger))
    issues.extend(_lint_trade_levels(markdown))
    issues.extend(_lint_rating_action(markdown))
    issues.extend(_lint_news_causality(markdown, validation_report))
    issues.extend(_lint_no_news_claim(markdown, source_registry))
    issues.extend(_lint_evidence_grounding(claims, metrics_packet, evidence_ledger))
    issues.extend(_lint_decision_permission(markdown, decision_packet))
    issues.extend(_lint_unsupported_guidance_claims(markdown, evidence_ledger))
    issues.extend(_lint_unsupported_earnings_claims(markdown, validation_report))
    issues.extend(
        _lint_financial_sanity(
            metrics_packet,
            ticker,
            validation_report=validation_report,
            source_registry=source_registry,
            evidence_ledger=evidence_ledger,
            canonical_financials=canonical_financials,
            reconciliation_warnings=reconciliation_warnings,
            deeptech_assessment=deeptech_assessment,
        )
    )
    issues.extend(_lint_company_defined_fcf(metrics_packet, canonical_financials, ticker))
    issues.extend(_lint_company_defined_fcf_ocf(metrics_packet, canonical_financials))
    issues.extend(_lint_current_period_priority(metrics_packet, ticker))
    issues.extend(
        _lint_missing_fcf_rating_support(
            metrics_packet,
            markdown,
            decision_packet,
            ticker,
            canonical_financials=canonical_financials,
        )
    )
    issues.extend(_lint_fcf_unavailable_support(metrics_packet, canonical_financials, ticker))
    issues.extend(_lint_current_period_context(markdown, canonical_financials, ticker))
    issues.extend(_lint_avgo_current_kpi_context(markdown, canonical_financials, ticker))
    issues.extend(_mirror_validation_warnings(validation_report, markdown))
    issues.extend(deeptech_assessment.issues)

    return AuditReport.from_issues(issues=issues, numeric_claims=claims, ticker=ticker)


def audit_report_from_files(
    report_path: Union[str, Path],
    metrics_path: Union[str, Path],
    validation_path: Optional[Union[str, Path]] = None,
    sources_path: Optional[Union[str, Path]] = None,
    evidence_path: Optional[Union[str, Path]] = None,
) -> AuditReport:
    markdown = Path(report_path).read_text(encoding="utf-8")
    metrics = MetricsPacket(**_load_json(metrics_path))
    validation = ValidationReport(**_load_json(validation_path)) if validation_path else None
    sources = SourceRegistry(**_load_json(sources_path)) if sources_path else None
    evidence = load_evidence_ledger(evidence_path) if evidence_path else None
    return audit_markdown_report(
        markdown=markdown,
        metrics_packet=metrics,
        validation_report=validation,
        source_registry=sources,
        evidence_ledger=evidence,
        ticker=metrics.ticker,
    )


def _lint_numeric_claims(
    claims: list[ExtractedNumericClaim],
    metrics_packet: MetricsPacket,
    evidence_ledger: Optional[EvidenceLedger] = None,
) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    for claim in claims:
        if claim.unit == "date":
            continue
        mapped = map_claim_to_metric(claim, metrics_packet)
        if mapped is None:
            if _looks_like_unverified_hard_metric(claim):
                if _has_direct_evidence_for_numeric_claim(claim, evidence_ledger):
                    continue
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="UNVERIFIED_HARD_METRIC",
                        message="Report contains a hard numeric metric that could not be mapped to MetricsPacket.",
                        line_number=claim.line_number,
                        raw_text=claim.raw_text,
                    )
                )
            continue

        if _has_period_mismatch(claim, mapped.metric_name):
            issues.append(
                AuditIssue(
                    severity="error",
                    code="PERIOD_MISMATCH",
                    metric=_base_metric_name(mapped.metric_name),
                    message="Report mixes Q4 and TTM period language for a validated metric.",
                    line_number=claim.line_number,
                    raw_text=claim.raw_text,
                )
            )

        if mapped.validated_value is None or claim.normalized_value is None:
            issues.append(
                AuditIssue(
                    severity="warning",
                    code="UNVERIFIED_HARD_METRIC",
                    metric=mapped.metric_name,
                    message="Mapped metric is unavailable in validated MetricsPacket.",
                    line_number=claim.line_number,
                    raw_text=claim.raw_text,
                )
            )
            continue

        reported_value = _comparable_reported_value(claim, mapped.validated_value)
        if not _numbers_match(reported_value, mapped.validated_value, claim.unit):
            nearby = claim.nearby_text.lower()
            if claim.raw_text.lower() in {"$1m", "$1 m"} and "customers above" in nearby:
                continue
            if _has_direct_evidence_for_numeric_claim(claim, evidence_ledger):
                continue
            issues.append(
                AuditIssue(
                    severity="error",
                    code="NUMERIC_MISMATCH",
                    metric=mapped.metric_name,
                    reported=reported_value,
                    validated=mapped.validated_value,
                    message=(
                        f"Report states {mapped.metric_name} as {claim.raw_text} "
                        f"but validated MetricsPacket has {mapped.validated_value}."
                    ),
                    line_number=claim.line_number,
                    raw_text=claim.raw_text,
                )
            )
    return issues


def _lint_trade_levels(markdown: str) -> list[AuditIssue]:
    setup = _extract_trade_setup(markdown)
    if setup is None:
        return []
    return [
        AuditIssue(
            severity=issue["severity"],
            code=_audit_trade_rule_code(issue["code"]),
            message=issue["message"],
            metric="trade_levels",
        )
        for issue in validate_trade_levels(**setup)
    ]


def _audit_trade_rule_code(_: str) -> str:
    return "INVALID_TRADE_LEVEL"


def _lint_rating_action(markdown: str) -> list[AuditIssue]:
    rating = extract_final_rating(markdown)
    actions = extract_action_lines(markdown)
    action_class = infer_report_action_class(actions)
    if rating is None or action_class == "unknown":
        return []

    rating_lower = rating.lower()
    if rating_lower == "sell" and action_class == "tactical_trim":
        return [
            AuditIssue(
                severity="error",
                code="RATING_TOO_HARSH_FOR_ACTION",
                metric="rating",
                message="Final rating is Sell, but operative actions imply tactical trim rather than full exit.",
            )
        ]
    if rating_lower in {"sell", "underweight"} and action_class == "tactical_trim":
        return [
            AuditIssue(
                severity="warning",
                code="RATING_TOO_HARSH_FOR_ACTION",
                metric="rating",
                message=f"Final rating is {rating}, but operative actions imply tactical trim.",
            )
        ]
    if rating_lower == "buy" and action_class == "staged_entry":
        return [
            AuditIssue(
                severity="warning",
                code="RATING_ACTION_MISMATCH",
                metric="rating",
                message="Final rating is Buy, but operative actions imply staged accumulation.",
            )
        ]
    return []


def _lint_news_causality(
    markdown: str,
    validation_report: Optional[ValidationReport],
) -> list[AuditIssue]:
    if not (CAUSALITY_RE.search(markdown) and PRICE_NEWS_RE.search(markdown)):
        return []
    codes = {issue.code for issue in validation_report.issues} if validation_report else set()
    if "NEWS_PRICE_CAUSALITY_CONFIRMED" in codes:
        return []
    return [
        AuditIssue(
            severity="warning",
            code="OVERSTATED_CAUSALITY",
            message="Report implies direct causality between news and price movement, but validator did not confirm same-day relationship.",
        )
    ]


def _lint_no_news_claim(
    markdown: str,
    source_registry: Optional[SourceRegistry],
) -> list[AuditIssue]:
    if not NO_NEWS_RE.search(markdown) or source_registry is None:
        return []
    relevant_sources = [
        source
        for source in source_registry.sources
        if source.source_type in {"company_ir", "sec_filing", "reuters", "barrons", "marketwatch", "earnings_transcript"}
        or "news" in source.used_for
    ]
    if not relevant_sources:
        return []
    return [
        AuditIssue(
            severity="error",
            code="NO_NEWS_WITH_AVAILABLE_SOURCES",
            message="Report claims no news, but SourceRegistry contains relevant sources.",
        )
    ]


def _lint_evidence_grounding(
    claims: list[ExtractedNumericClaim],
    metrics_packet: MetricsPacket,
    evidence_ledger: Optional[EvidenceLedger],
) -> list[AuditIssue]:
    if evidence_ledger is None:
        return []
    issues: list[AuditIssue] = []
    seen: set[tuple[str, str]] = set()
    for claim in claims:
        mapped = map_claim_to_metric(claim, metrics_packet)
        if mapped is None or mapped.metric_name is None:
            if _looks_like_unverified_hard_metric(claim):
                if _has_direct_evidence_for_numeric_claim(claim, evidence_ledger):
                    continue
                key = ("unmapped", str(claim.line_number))
                if key not in seen:
                    issues.append(
                        AuditIssue(
                            severity="error",
                            code="MISSING_EVIDENCE_FOR_HARD_CLAIM",
                            message="Hard numeric claim cannot be mapped to validated metrics or evidence.",
                            line_number=claim.line_number,
                            raw_text=claim.raw_text,
                        )
                    )
                    seen.add(key)
            continue

        metric_name = mapped.metric_name
        evidence_issue = validate_metric_evidence(metric_name, evidence_ledger)
        if evidence_issue:
            code = (
                "MISSING_EVIDENCE_FOR_HARD_CLAIM"
                if evidence_issue["code"] == "MISSING_EVIDENCE_FOR_METRIC"
                else "LOW_AUTHORITY_EVIDENCE_FOR_HARD_CLAIM"
            )
            key = (code, metric_name)
            if key not in seen:
                issues.append(
                    AuditIssue(
                        severity="error" if code == "MISSING_EVIDENCE_FOR_HARD_CLAIM" else "warning",
                        code=code,
                        metric=metric_name,
                        message=evidence_issue["message"],
                        line_number=claim.line_number,
                        raw_text=claim.raw_text,
                    )
                )
                seen.add(key)

        vendor_issue = validate_vendor_not_primary(metric_name, evidence_ledger)
        if vendor_issue:
            key = ("VENDOR_SOURCE_USED_AS_PRIMARY", metric_name)
            if key not in seen:
                issues.append(
                    AuditIssue(
                        severity="warning",
                        code="VENDOR_SOURCE_USED_AS_PRIMARY",
                        metric=metric_name,
                        message=vendor_issue["message"],
                        line_number=claim.line_number,
                        raw_text=claim.raw_text,
                    )
                )
                seen.add(key)
    return issues


def _has_direct_evidence_for_numeric_claim(
    claim: ExtractedNumericClaim,
    evidence_ledger: Optional[EvidenceLedger],
) -> bool:
    if evidence_ledger is None or claim.normalized_value is None:
        return False
    nearby = claim.nearby_text.lower()
    for item in evidence_ledger.evidence_items:
        if item.value is None:
            continue
        if not _numbers_close_for_evidence(float(claim.normalized_value), float(item.value)):
            continue
        haystack = " ".join(
            [
                item.evidence_id,
                item.statement,
                item.period or "",
                item.unit or "",
                " ".join(item.supports_metrics),
            ]
        ).lower()
        tokens = [token for token in re.split(r"[^a-z0-9]+", nearby) if len(token) >= 3]
        if any(token in haystack for token in tokens):
            return True
        if "nrr" in nearby and any("net_revenue_retention" in metric for metric in item.supports_metrics):
            return True
    return False


def _numbers_close_for_evidence(reported: float, evidence_value: float) -> bool:
    if evidence_value == 0:
        return abs(reported) < 1e-9
    if 0 < abs(evidence_value) <= 2 and abs(reported) > 10:
        reported = reported / 100
    return abs(reported - evidence_value) / abs(evidence_value) <= 0.015


def _lint_decision_permission(
    markdown: str,
    decision_packet: Optional[DecisionPacket],
) -> list[AuditIssue]:
    if decision_packet is None:
        return []
    rating = extract_rating_from_text(markdown)
    if rating is None:
        return []
    if rating in decision_packet.rating_permission.blocked_ratings:
        return [
            AuditIssue(
                severity="error",
                code="RATING_BLOCKED_BY_DECISION_PACKET",
                metric="rating",
                message=f"Final rating {rating.value} is blocked by DecisionPacket.",
            )
        ]
    return []


def _lint_unsupported_guidance_claims(
    markdown: str,
    evidence_ledger: Optional[EvidenceLedger],
) -> list[AuditIssue]:
    if evidence_ledger is None or not GUIDANCE_CLAIM_RE.search(markdown) or GUIDANCE_UNAVAILABLE_RE.search(markdown):
        return []
    guidance_items = [
        item
        for item in evidence_ledger.evidence_items
        if (
            "guidance" in item.claim_type
            or any("guidance" in metric for metric in item.supports_metrics)
            or "guide" in item.statement.lower()
            or "guidance" in item.statement.lower()
        )
    ] if evidence_ledger else []
    primary_guidance = [
        item
        for item in guidance_items
        if item.source_type in {"company_ir", "earnings_release", "sec_filing", "official_press_release"}
    ]
    if primary_guidance:
        return []
    return [
        AuditIssue(
            severity="error",
            code="UNSUPPORTED_GUIDANCE_CLAIM",
            metric="company_guidance_eps",
            message="Report makes a guidance claim, but no company guidance evidence is available.",
        )
    ]


def _lint_unsupported_earnings_claims(
    markdown: str,
    validation_report: Optional[ValidationReport],
) -> list[AuditIssue]:
    if not EARNINGS_EVENT_RISK_RE.search(markdown) or EARNINGS_UNAVAILABLE_RE.search(markdown):
        return []
    codes = {issue.code for issue in validation_report.issues} if validation_report else set()
    if codes.intersection({"EARNINGS_DATE_UNAVAILABLE", "EARNINGS_DATE_UNCONFIRMED"}):
        return [
            AuditIssue(
                severity="error",
                code="UNSUPPORTED_EARNINGS_EVENT_CLAIM",
                metric="next_earnings_date",
                message="Report makes an earnings event-risk claim without a confirmed earnings date.",
            )
        ]
    return []


def _lint_financial_sanity(
    metrics_packet: MetricsPacket,
    ticker: Optional[str],
    *,
    validation_report: Optional[ValidationReport] = None,
    source_registry: Optional[SourceRegistry] = None,
    evidence_ledger: Optional[EvidenceLedger] = None,
    canonical_financials: Optional[CanonicalFinancials] = None,
    reconciliation_warnings: Optional[list[dict]] = None,
    deeptech_assessment: Any = None,
) -> list[AuditIssue]:
    ticker = (ticker or metrics_packet.ticker or "").upper()
    fundamentals = metrics_packet.fundamentals
    valuation = metrics_packet.valuation
    issues: list[AuditIssue] = []
    sector = _sector_profile(ticker)
    ev_sales_issue_emitted = False

    denominator_bug_reason = _valuation_denominator_bug_reason(
        metrics_packet=metrics_packet,
        validation_report=validation_report,
        canonical_financials=canonical_financials,
        reconciliation_warnings=reconciliation_warnings,
    )
    valuation_inputs_backed = _valuation_inputs_evidence_backed(
        metrics_packet=metrics_packet,
        source_registry=source_registry,
        evidence_ledger=evidence_ledger,
    )
    early_commercial_capital_intensive = (
        getattr(deeptech_assessment, "company_archetype", None)
        == CompanyArchetype.EARLY_COMMERCIAL_CAPITAL_INTENSIVE_TECH
    )

    if valuation.ev_to_sales is not None and valuation.ev_to_sales > 100:
        if denominator_bug_reason:
            issues.append(
                AuditIssue(
                    severity="error",
                    code="PERIOD_DENOMINATOR_BUG",
                    metric="ev_to_sales",
                    reported=valuation.ev_to_sales,
                    message=f"EV/Sales above 100x has a concrete denominator/period/unit bug signal: {denominator_bug_reason}",
                )
            )
        else:
            source_phrase = "with revenue and valuation inputs evidence-backed" if valuation_inputs_backed else "without a concrete denominator bug signal"
            issues.append(
                AuditIssue(
                    severity="error",
                    code="EXTREME_VALUATION_REQUIRES_REVIEW",
                    metric="ev_to_sales",
                    reported=valuation.ev_to_sales,
                    message=(
                        f"EV/Sales above 100x is an extreme valuation {source_phrase}; "
                        "treat it as valuation risk, not an automatic period-denominator bug."
                    ),
                )
            )
        ev_sales_issue_emitted = True
    elif valuation.ev_to_sales is not None:
        warning_threshold, block_threshold = _ev_sales_thresholds(sector)
        if early_commercial_capital_intensive:
            block_threshold = min(block_threshold, 50.0)
        if valuation.ev_to_sales > block_threshold:
            if denominator_bug_reason:
                issues.append(
                    AuditIssue(
                        severity="error",
                        code="PERIOD_DENOMINATOR_BUG",
                        metric="ev_to_sales",
                        reported=valuation.ev_to_sales,
                        message=f"EV/Sales has a concrete denominator/period/unit bug signal: {denominator_bug_reason}",
                    )
                )
            else:
                profile_phrase = " for an early-commercial capital-intensive technology profile" if early_commercial_capital_intensive else f" for {sector}"
                issues.append(
                    AuditIssue(
                        severity="error",
                        code="TRUE_VALUATION_ANOMALY",
                        metric="ev_to_sales",
                        reported=valuation.ev_to_sales,
                        message=(
                            f"EV/Sales above {block_threshold}x is a clean but fundamentally notable valuation anomaly{profile_phrase}; "
                            "review backlog, revenue growth, execution risk and FCF path before publish."
                        ),
                    )
                )
            ev_sales_issue_emitted = True
        elif valuation.ev_to_sales > warning_threshold:
            issues.append(
                AuditIssue(
                    severity="warning",
                    code="GUARD_THRESHOLD_REVIEW",
                    metric="ev_to_sales",
                    reported=valuation.ev_to_sales,
                    message=f"EV/Sales above {warning_threshold}x should be reviewed in {sector} context.",
                )
            )

    if fundamentals.sbc_to_revenue is not None and fundamentals.sbc_to_revenue > 1.0:
        sbc_denominator_bug_reason = _ratio_denominator_bug_reason(
            validation_report=validation_report,
            reconciliation_warnings=reconciliation_warnings,
            metric_terms={"sbc", "stock-based compensation", "stock based compensation", "sbc_to_revenue", "revenue"},
        )
        code = "PERIOD_DENOMINATOR_BUG" if sbc_denominator_bug_reason else "TRUE_FINANCIAL_ANOMALY"
        message = (
            f"SBC/Revenue above 100% has a concrete denominator/period/unit bug signal: {sbc_denominator_bug_reason}"
            if sbc_denominator_bug_reason
            else f"SBC/Revenue above 100% is extreme for {sector} without a concrete denominator bug signal."
        )
        issues.append(
            AuditIssue(
                severity="error",
                code=code,
                metric="sbc_to_revenue",
                reported=fundamentals.sbc_to_revenue,
                message=message,
            )
        )
    elif fundamentals.sbc_to_revenue is not None:
        warning_threshold, block_threshold = _sbc_thresholds(sector)
        if fundamentals.sbc_to_revenue > block_threshold:
            issues.append(
                AuditIssue(
                    severity="error",
                    code="TRUE_FINANCIAL_ANOMALY",
                    metric="sbc_to_revenue",
                    reported=fundamentals.sbc_to_revenue,
                    message=f"SBC/Revenue above {block_threshold:.0%} is extreme for {sector} after period compatibility checks.",
                )
            )
        elif fundamentals.sbc_to_revenue > warning_threshold:
            issues.append(
                AuditIssue(
                    severity="warning",
                    code="GUARD_THRESHOLD_REVIEW",
                    metric="sbc_to_revenue",
                    reported=fundamentals.sbc_to_revenue,
                    message=f"SBC/Revenue above {warning_threshold:.0%} should be reviewed in {sector} context.",
                )
            )

    if valuation.price_to_fcf is not None and valuation.price_to_fcf > 100 and _fcf_denominator_clean(fundamentals.free_cash_flow_ttm):
        issues.append(
            AuditIssue(
                severity="error",
                code="FINANCIAL_SANITY_PRICE_TO_FCF_ANOMALY",
                metric="price_to_fcf",
                reported=valuation.price_to_fcf,
                message="P/FCF above 100x on positive, non-near-zero FCF requires explicit explanation before publish.",
            )
        )
        issues.append(
            AuditIssue(
                severity="error",
                code="TRUE_FINANCIAL_ANOMALY",
                metric="price_to_fcf",
                reported=valuation.price_to_fcf,
                message="P/FCF above 100x on positive, non-near-zero FCF requires explicit explanation before publish.",
            )
        )

    if fundamentals.fcf_margin_ttm is not None and fundamentals.fcf_margin_ttm > 1.0:
        issues.append(
            AuditIssue(
                severity="error",
                code="PERIOD_DENOMINATOR_BUG",
                metric="fcf_margin_ttm",
                reported=fundamentals.fcf_margin_ttm,
                message="FCF margin above 100% indicates a likely FCF/revenue period denominator mismatch.",
            )
        )
    elif fundamentals.fcf_margin_ttm is not None and fundamentals.fcf_margin_ttm > 0.40 and _requires_fcf_margin_sanity(ticker):
        issues.append(
            AuditIssue(
                severity="warning",
                code="FINANCIAL_SANITY_FCF_MARGIN_ANOMALY",
                metric="fcf_margin_ttm",
                reported=fundamentals.fcf_margin_ttm,
                message="FCF margin above 40% requires sector-context review.",
            )
        )
        issues.append(
            AuditIssue(
                severity="warning",
                code="GUARD_THRESHOLD_REVIEW",
                metric="fcf_margin_ttm",
                reported=fundamentals.fcf_margin_ttm,
                message="FCF margin above 40% should be reviewed in sector context.",
            )
        )

    if (
        valuation.market_cap is not None
        and fundamentals.revenue_ttm is not None
        and fundamentals.revenue_ttm > 0
        and valuation.market_cap / fundamentals.revenue_ttm > 100
    ):
        market_cap_to_revenue = valuation.market_cap / fundamentals.revenue_ttm
        if denominator_bug_reason:
            issues.append(
                AuditIssue(
                    severity="error",
                    code="PERIOD_DENOMINATOR_BUG",
                    metric="market_cap_to_revenue",
                    reported=market_cap_to_revenue,
                    message=f"Market cap to revenue above 100x has a concrete denominator/period/unit bug signal: {denominator_bug_reason}",
                )
            )
        elif not ev_sales_issue_emitted:
            source_phrase = "with revenue and valuation inputs evidence-backed" if valuation_inputs_backed else "without a concrete denominator bug signal"
            issues.append(
                AuditIssue(
                    severity="error",
                    code="EXTREME_VALUATION_REQUIRES_REVIEW",
                    metric="market_cap_to_revenue",
                    reported=market_cap_to_revenue,
                    message=(
                        f"Market cap to revenue above 100x is an extreme valuation {source_phrase}; "
                        "treat it as valuation risk, not an automatic period-denominator bug."
                    ),
                )
            )
    return issues


def _valuation_denominator_bug_reason(
    *,
    metrics_packet: MetricsPacket,
    validation_report: Optional[ValidationReport],
    canonical_financials: Optional[CanonicalFinancials],
    reconciliation_warnings: Optional[list[dict]],
) -> Optional[str]:
    fundamentals = metrics_packet.fundamentals
    valuation = metrics_packet.valuation
    revenue_ttm = fundamentals.revenue_ttm

    if revenue_ttm is None or revenue_ttm <= 0:
        return "revenue_ttm denominator is missing or non-positive."

    if valuation.ev_to_sales is not None and valuation.enterprise_value is not None:
        expected_ev_sales = valuation.enterprise_value / revenue_ttm
        if not _numbers_close(expected_ev_sales, valuation.ev_to_sales, relative_tolerance=0.05, absolute_tolerance=0.10):
            return "EV/Sales does not reconcile to enterprise_value / revenue_ttm."

    if valuation.market_cap is not None and valuation.enterprise_value is not None and valuation.market_cap > 0:
        ev_to_market_cap = abs(valuation.enterprise_value) / valuation.market_cap
        if ev_to_market_cap > 10 or ev_to_market_cap < 0.10:
            return "enterprise_value and market_cap are on incompatible source scales."

    validation_reason = _valuation_bug_signal_from_validation(validation_report, reconciliation_warnings)
    if validation_reason:
        return validation_reason

    bucket_reason = _revenue_denominator_bucket_reason(canonical_financials, revenue_ttm)
    if bucket_reason:
        return bucket_reason

    return None


def _valuation_bug_signal_from_validation(
    validation_report: Optional[ValidationReport],
    reconciliation_warnings: Optional[list[dict]],
) -> Optional[str]:
    raw_issues: list[Any] = []
    if validation_report is not None:
        raw_issues.extend(validation_report.issues)
    raw_issues.extend(reconciliation_warnings or [])

    for issue in raw_issues:
        code = _issue_field(issue, "code").upper()
        severity = _issue_field(issue, "severity").lower()
        metric = _issue_field(issue, "metric").lower()
        message = _issue_field(issue, "message").lower()
        if "IGNORED" in code or severity in {"info", "debug"}:
            continue
        if not _valuation_denominator_relevant_metric(metric, message):
            continue
        strong_code = code in {
            "PERIOD_MISMATCH",
            "TTM_SUM_MISMATCH",
            "PERIOD_DENOMINATOR_BUG",
            "SOURCE_SCALE_MISMATCH",
            "UNIT_PARSE_PROBLEM",
            "REVENUE_BUCKET_MISMATCH",
        }
        strong_text = any(
            term in f"{code.lower()} {message}"
            for term in ["period mismatch", "denominator", "wrong bucket", "unit", "scale mismatch", "ttm/q", "quarterly as ttm"]
        )
        if severity == "error" and (strong_code or strong_text):
            return _issue_field(issue, "message") or code
        if strong_code and severity in {"warning", "blocker"}:
            return _issue_field(issue, "message") or code
    return None


def _ratio_denominator_bug_reason(
    *,
    validation_report: Optional[ValidationReport],
    reconciliation_warnings: Optional[list[dict]],
    metric_terms: set[str],
) -> Optional[str]:
    raw_issues: list[Any] = []
    if validation_report is not None:
        raw_issues.extend(validation_report.issues)
    raw_issues.extend(reconciliation_warnings or [])

    normalized_terms = {term.lower() for term in metric_terms}
    for issue in raw_issues:
        code = _issue_field(issue, "code").upper()
        severity = _issue_field(issue, "severity").lower()
        metric = _issue_field(issue, "metric").lower()
        message = _issue_field(issue, "message").lower()
        if "IGNORED" in code or severity in {"info", "debug"}:
            continue
        haystack = f"{metric} {message}"
        if not any(term in haystack for term in normalized_terms):
            continue
        strong_code = code in {
            "PERIOD_MISMATCH",
            "TTM_SUM_MISMATCH",
            "PERIOD_DENOMINATOR_BUG",
            "SOURCE_SCALE_MISMATCH",
            "UNIT_PARSE_PROBLEM",
            "REVENUE_BUCKET_MISMATCH",
        }
        strong_text = any(
            term in f"{code.lower()} {message}"
            for term in ["period mismatch", "denominator", "wrong bucket", "unit", "scale mismatch", "ttm/q", "quarterly as ttm"]
        )
        if severity == "error" and (strong_code or strong_text):
            return _issue_field(issue, "message") or code
        if strong_code and severity in {"warning", "blocker"}:
            return _issue_field(issue, "message") or code
    return None


def _valuation_denominator_relevant_metric(metric: str, message: str) -> bool:
    haystack = f"{metric} {message}"
    return any(
        term in haystack
        for term in [
            "revenue",
            "sales",
            "ev/sales",
            "ev_to_sales",
            "enterprise value",
            "enterprise_value",
            "market cap",
            "market_cap",
        ]
    )


def _revenue_denominator_bucket_reason(
    canonical_financials: Optional[CanonicalFinancials],
    revenue_ttm: float,
) -> Optional[str]:
    if canonical_financials is None:
        return None
    matches = [
        metric
        for metric in canonical_financials.metrics_for("revenue")
        if _numbers_close(metric.value, revenue_ttm, relative_tolerance=0.01, absolute_tolerance=1_000_000)
    ]
    if not matches:
        return None
    clean_duration = [
        metric
        for metric in matches
        if metric.period_bucket in {"ttm", "annual"} or (metric.duration_days is not None and metric.duration_days >= 330)
    ]
    if clean_duration:
        return None
    wrong_bucket = [
        metric
        for metric in matches
        if metric.period_bucket in {"quarterly", "ytd"} or (metric.duration_days is not None and metric.duration_days < 330)
    ]
    if wrong_bucket:
        metric = wrong_bucket[0]
        return f"revenue_ttm matches {metric.period_bucket} revenue period {metric.period}, not a TTM/annual denominator."
    return None


def _valuation_inputs_evidence_backed(
    *,
    metrics_packet: MetricsPacket,
    source_registry: Optional[SourceRegistry],
    evidence_ledger: Optional[EvidenceLedger],
) -> bool:
    fundamentals = metrics_packet.fundamentals
    valuation = metrics_packet.valuation
    if fundamentals.revenue_ttm is None or fundamentals.revenue_ttm <= 0:
        return False
    if valuation.market_cap is None or valuation.enterprise_value is None:
        return False
    revenue_backed = _has_high_authority_metric_source({"revenue", "revenue_ttm", "sales"}, source_registry, evidence_ledger)
    price_backed = _has_high_authority_metric_source({"price", "close", "price_data", "price_basis"}, source_registry, evidence_ledger)
    shares_backed = _has_high_authority_metric_source({"shares", "diluted_share_count", "share_count"}, source_registry, evidence_ledger)
    ev_components_backed = _has_high_authority_metric_source({"debt", "total_debt", "net_debt"}, source_registry, evidence_ledger) and _has_high_authority_metric_source(
        {"cash", "cash_and_equivalents", "cash_and_investments", "net_cash"},
        source_registry,
        evidence_ledger,
    )
    return revenue_backed and price_backed and shares_backed and ev_components_backed


def _has_high_authority_metric_source(
    metric_names: set[str],
    source_registry: Optional[SourceRegistry],
    evidence_ledger: Optional[EvidenceLedger],
) -> bool:
    normalized = {name.lower() for name in metric_names}
    if evidence_ledger is not None:
        for name in normalized:
            if any((item.authority_rank or 99) <= 2 for item in evidence_ledger.find_by_metric(name)):
                return True
    if source_registry is not None:
        for source in source_registry.sources:
            authority = source.resolved_authority_rank() if hasattr(source, "resolved_authority_rank") else (source.authority_rank or 99)
            if authority > 2:
                continue
            used_for = {item.lower() for item in source.used_for}
            if used_for.intersection(normalized):
                return True
    return False


def _issue_field(issue: Any, field_name: str) -> str:
    if isinstance(issue, dict):
        return str(issue.get(field_name) or "")
    return str(getattr(issue, field_name, "") or "")


def _numbers_close(
    left: float,
    right: float,
    *,
    relative_tolerance: float,
    absolute_tolerance: float,
) -> bool:
    return abs(left - right) <= max(absolute_tolerance, abs(right) * relative_tolerance)


def _lint_company_defined_fcf_ocf(
    metrics_packet: MetricsPacket,
    canonical_financials: Optional[CanonicalFinancials],
) -> list[AuditIssue]:
    if canonical_financials is None:
        return []
    company_fcf = _latest_company_metric(canonical_financials, {"free_cash_flow", "adjusted_free_cash_flow"})
    company_ocf = _latest_company_metric(canonical_financials, {"operating_cash_flow"})
    if company_fcf is None or company_ocf is None or company_ocf.value <= 0:
        return []
    if not _periods_compatible_for_fcf_ocf(company_fcf, company_ocf):
        return []
    if company_fcf.value <= company_ocf.value * 1.01:
        return []
    diff_pct = (company_fcf.value / company_ocf.value) - 1
    severity = "error" if diff_pct > 0.05 else "warning"
    return [
        AuditIssue(
            severity=severity,
            code="COMPANY_DEFINED_FCF_OCF_INCONSISTENCY",
            metric="free_cash_flow_ttm",
            reported=company_fcf.value,
            validated=company_ocf.value,
            message=(
                "Company-defined FCF exceeds company-defined operating cash flow for the matched current period; "
                "reconcile OCF, capex and FCF definitions before external publication."
            ),
        )
    ]


def _latest_company_metric(canonical_financials: CanonicalFinancials, metric_names: set[str]):
    candidates = [
        metric
        for metric in canonical_financials.metrics
        if metric.metric_name in metric_names
        and metric.basis in {"company_defined", "non_gaap", "gaap"}
        and any("IR" in source_id or "EARNINGS" in source_id for source_id in metric.source_ids)
    ]
    if not candidates:
        return None
    candidates = sorted(candidates, key=lambda metric: (metric.end_date or "", metric.period or ""), reverse=True)
    return candidates[0]


def _periods_compatible_for_fcf_ocf(fcf_metric, ocf_metric) -> bool:
    if fcf_metric.period == ocf_metric.period:
        return True
    if fcf_metric.start_date and ocf_metric.start_date and fcf_metric.end_date and ocf_metric.end_date:
        return fcf_metric.start_date == ocf_metric.start_date and fcf_metric.end_date == ocf_metric.end_date
    return fcf_metric.period_bucket == ocf_metric.period_bucket and fcf_metric.period_bucket in {"annual", "ttm"}


def _sector_profile(ticker: str) -> str:
    if ticker in {"DDOG", "MDB", "SNOW", "CRWD", "NET", "ZS", "CRM", "NOW", "ADBE", "INTU"}:
        return "saas"
    if ticker in {"NVDA", "AMD", "AVGO", "INTC", "QCOM", "MU", "MRVL", "ANET"}:
        return "semiconductors"
    if ticker in {"AMZN", "MSFT", "GOOGL", "META", "AAPL", "NFLX"}:
        return "mega_cap_tech"
    return "general"


def _ev_sales_thresholds(sector: str) -> tuple[float, float]:
    if sector == "saas":
        return 40.0, 80.0
    if sector == "mega_cap_tech":
        return 25.0, 50.0
    if sector == "semiconductors":
        return 30.0, 60.0
    return 30.0, 80.0


def _sbc_thresholds(sector: str) -> tuple[float, float]:
    if sector == "saas":
        return 0.30, 0.50
    if sector == "mega_cap_tech":
        return 0.15, 0.30
    return 0.30, 0.50


def _fcf_denominator_clean(fcf: Optional[float]) -> bool:
    return fcf is not None and fcf > 1_000_000_000


CURRENT_PERIOD_REFERENCE_METRICS = {
    "AMZN": {
        "free_cash_flow_ttm": 1_232_000_000.0,
        "tolerance": 0.10,
        "source_label": "company Q1 2026 FCF reconciliation",
    },
    "DDOG": {
        "revenue_ttm": 3_430_000_000.0,
        "free_cash_flow_ttm": 915_000_000.0,
        "tolerance": 0.05,
        "source_label": "company FY2025 release",
    },
    "CRM": {
        "revenue_ttm": 41_500_000_000.0,
        "free_cash_flow_ttm": 14_400_000_000.0,
        "tolerance": 0.05,
        "source_label": "company FY2026 release",
    },
}


def _lint_current_period_priority(
    metrics_packet: MetricsPacket,
    ticker: Optional[str],
) -> list[AuditIssue]:
    ticker = (ticker or metrics_packet.ticker or "").upper()
    if metrics_packet.as_of_date != "2026-05-05":
        return []
    reference = CURRENT_PERIOD_REFERENCE_METRICS.get(ticker)
    if not reference:
        return []
    issues: list[AuditIssue] = []
    fundamentals = metrics_packet.fundamentals
    tolerance = float(reference["tolerance"])
    for metric_name in ["revenue_ttm", "free_cash_flow_ttm"]:
        if metric_name not in reference:
            continue
        packet_value = getattr(fundamentals, metric_name)
        official_value = reference[metric_name]
        if packet_value is None:
            continue
        if abs(packet_value - official_value) / official_value > tolerance:
            issues.append(
                AuditIssue(
                    severity="error",
                    code="CURRENT_PERIOD_IR_RECONCILIATION_REQUIRED",
                    metric=metric_name,
                    reported=packet_value,
                    validated=official_value,
                    message=(
                        f"{ticker} {metric_name} differs materially from {reference['source_label']}; "
                        "current-period IR/company-defined values must be reconciled before publish."
                    ),
                )
            )
    return issues


def _lint_company_defined_fcf(
    metrics_packet: MetricsPacket,
    canonical_financials: Optional[CanonicalFinancials],
    ticker: Optional[str],
) -> list[AuditIssue]:
    if canonical_financials is None:
        return []
    company_fcf = _best_company_defined_fcf(canonical_financials)
    if company_fcf is None:
        return []
    packet_fcf = metrics_packet.fundamentals.free_cash_flow_ttm
    if packet_fcf is None:
        return []
    if company_fcf.value == 0:
        return []
    diff = abs(packet_fcf - company_fcf.value) / abs(company_fcf.value)
    if diff <= 0.10:
        return []
    return [
        AuditIssue(
            severity="error",
            code="COMPANY_DEFINED_FCF_MISMATCH",
            metric="free_cash_flow_ttm",
            reported=packet_fcf,
            validated=company_fcf.value,
            message=(
                f"{(ticker or metrics_packet.ticker or '').upper()} packet FCF differs from company-defined IR/Earnings Release FCF by more than 10%; "
                "company-defined FCF must override SEC-derived FCF before publish."
            ),
        )
    ]


def _best_company_defined_fcf(canonical_financials: CanonicalFinancials):
    candidates = [
        metric for metric in canonical_financials.metrics
        if metric.metric_name in {"free_cash_flow", "adjusted_free_cash_flow"}
        and metric.basis in {"company_defined", "non_gaap"}
        and any("IR" in source_id or "EARNINGS" in source_id for source_id in metric.source_ids)
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda metric: (
            metric.end_date or "",
            1 if metric.metric_name == "free_cash_flow" else 0,
            {"high": 3, "medium": 2, "low": 1}.get(metric.confidence, 0),
        ),
        reverse=True,
    )[0]


def _lint_fcf_unavailable_support(
    metrics_packet: MetricsPacket,
    canonical_financials: Optional[CanonicalFinancials],
    ticker: Optional[str],
) -> list[AuditIssue]:
    ticker = (ticker or metrics_packet.ticker or "").upper()
    if metrics_packet.fundamentals.free_cash_flow_ttm is not None:
        return []
    sector = _sector_profile(ticker)
    if sector not in {"saas"} and ticker not in {"PANW"}:
        return []
    has_adjusted_support = False
    if canonical_financials is not None:
        has_adjusted_support = any(
            metric.metric_name in {"free_cash_flow", "adjusted_free_cash_flow", "adjusted_free_cash_flow_margin"}
            and metric.basis in {"company_defined", "non_gaap"}
            and any("IR" in source_id or "EARNINGS" in source_id for source_id in metric.source_ids)
            for metric in canonical_financials.metrics
        )
    if ticker == "PANW" or not has_adjusted_support:
        return [
            AuditIssue(
                severity="error",
                code="FCF_UNAVAILABLE_WITHOUT_IR_SUPPORT",
                metric="free_cash_flow_ttm",
                message=(
                    f"{ticker} has unavailable FCF in a FCF-relevant software/cybersecurity report; "
                    "the report must stay manual review unless current IR adjusted FCF support is reconciled and limitations are explicit."
                ),
            )
        ]
    return []


def _lint_current_period_context(
    markdown: str,
    canonical_financials: Optional[CanonicalFinancials],
    ticker: Optional[str],
) -> list[AuditIssue]:
    ticker = (ticker or "").upper()
    if canonical_financials is None or not _has_current_ir_metrics(canonical_financials):
        return []
    text = markdown.lower()
    required_terms = _current_period_terms(ticker)
    found = sum(1 for term in required_terms if term in text)
    if found >= 2:
        return []
    return [
        AuditIssue(
            severity="error",
            code="MISSING_CURRENT_PERIOD_KPI_CONTEXT",
            metric="current_period_context",
            message=(
                f"{ticker} has current-period IR/Earnings data, but the report lacks at least two ticker-specific current-period KPI claims."
            ),
        )
    ]


def _lint_avgo_current_kpi_context(
    markdown: str,
    canonical_financials: Optional[CanonicalFinancials],
    ticker: Optional[str],
) -> list[AuditIssue]:
    ticker = (ticker or "").upper()
    if ticker != "AVGO" or canonical_financials is None or not _has_current_ir_metrics(canonical_financials):
        return []
    text = markdown.lower()
    required_groups = [
        {"ai revenue", "ai semiconductor"},
        {"q2 revenue guide", "q2 revenue guidance", "q2 fy2026 revenue guide"},
        {"q1 fcf", "q1 free cash flow", "q1 fy2026 free cash flow"},
    ]
    if all(any(term in text for term in group) for group in required_groups):
        return []
    return [
        AuditIssue(
            severity="error",
            code="AVGO_CURRENT_KPI_CONTEXT_REQUIRED",
            metric="current_period_context",
            message="AVGO current-period Q1 AI revenue, Q2 guide and Q1 FCF must appear in the main report before publish.",
        )
    ]


def _has_current_ir_metrics(canonical_financials: CanonicalFinancials) -> bool:
    return any(
        any("IR" in source_id or "EARNINGS" in source_id for source_id in metric.source_ids)
        and metric.statement_type in {"income_statement", "cash_flow", "guidance"}
        for metric in canonical_financials.metrics
    )


def _current_period_terms(ticker: str) -> set[str]:
    if ticker == "GOOGL":
        return {"google cloud", "search", "capex", "fcf", "free cash flow", "other income"}
    if ticker == "SNOW":
        return {"product revenue", "rpo", "nrr", "net revenue retention", "free cash flow", "sbc"}
    if ticker == "META":
        return {"family of apps", "reality labs", "capex", "operating margin", "ai infrastructure"}
    if ticker == "MSFT":
        return {"azure", "intelligent cloud", "capex", "free cash flow", "operating margin"}
    if ticker == "AVGO":
        return {"ai semiconductor", "vmware", "infrastructure software", "free cash flow", "guidance"}
    return {"revenue", "free cash flow", "operating margin", "capex"}


def _lint_missing_fcf_rating_support(
    metrics_packet: MetricsPacket,
    markdown: str,
    decision_packet: Optional[DecisionPacket],
    ticker: Optional[str],
    canonical_financials: Optional[CanonicalFinancials] = None,
) -> list[AuditIssue]:
    preferred = decision_packet.rating_permission.preferred_rating if decision_packet else extract_rating_from_text(markdown)
    if preferred is None:
        return []
    if preferred.value not in {"Accumulate", "Buy", "Strong Buy"}:
        return []
    ticker_value = (ticker or metrics_packet.ticker or "").upper()
    fundamentals = metrics_packet.fundamentals
    fcf_available = fundamentals.free_cash_flow_ttm is not None
    if fcf_available:
        return []
    return [
        AuditIssue(
            severity="error",
            code="MISSING_FCF_SUPPORT_FOR_ACCUMULATE",
            metric="free_cash_flow_ttm",
            message=(
                f"{ticker_value} has Accumulate/Buy framing while FCF support is unavailable; "
                "current primary FCF evidence is required before plain Accumulate/Buy display."
            ),
        )
    ]


def _has_current_primary_cash_flow_support(
    canonical_financials: Optional[CanonicalFinancials],
    metric_names: set[str],
) -> bool:
    if canonical_financials is None:
        return False
    for metric in canonical_financials.metrics:
        if metric.metric_name not in metric_names:
            continue
        source_ids = " ".join(metric.source_ids).upper()
        if not ("CURRENT_PERIOD" in source_ids or "IR" in source_ids or "EARNINGS" in source_ids):
            continue
        if metric.statement_type == "cash_flow" and metric.confidence in {"high", "medium"}:
            return True
    return False


def _requires_sbc_sanity(ticker: str) -> bool:
    saas_exceptions = {"DDOG", "MDB", "SNOW", "CRWD", "NET", "ZS"}
    return ticker not in saas_exceptions


def _requires_fcf_margin_sanity(ticker: str) -> bool:
    high_margin_software = {"DDOG", "MDB", "SNOW", "CRWD", "NET", "ZS"}
    return ticker not in high_margin_software


def _mirror_validation_warnings(
    validation_report: Optional[ValidationReport],
    markdown: str,
) -> list[AuditIssue]:
    if validation_report is None:
        return []
    issues: list[AuditIssue] = []
    markdown_lower = markdown.lower()
    for issue in validation_report.issues:
        if issue.code == "FORWARD_EPS_GUIDANCE_MISMATCH" and ("eps" in markdown_lower or "kgv" in markdown_lower or "p/e" in markdown_lower):
            issues.append(
                AuditIssue(
                    severity=issue.severity,
                    code=issue.code,
                    metric=issue.metric or "forward_eps",
                    message=issue.message,
                )
            )
        if issue.code == "WEAK_NEWS_PRICE_CAUSALITY" and CAUSALITY_RE.search(markdown):
            issues.append(
                AuditIssue(
                    severity="warning",
                    code="WEAK_NEWS_CAUSALITY",
                    metric=issue.metric,
                    message=issue.message,
                )
            )
    return issues


def _extract_trade_setup(markdown: str) -> Optional[dict[str, Union[float, str]]]:
    text = " ".join(markdown.splitlines())
    lower = text.lower()
    position_type = "short" if "short" in lower and "long" not in lower else "long"
    entry = _extract_labeled_number(text, ["entry", "einstieg", "einstiegskurs"])
    stop = _extract_labeled_number(text, ["stop-loss", "stop loss", "stop"])
    target = _extract_labeled_number(text, ["take-profit", "take profit", "kursziel", "target"])
    if entry is None or stop is None:
        return None
    setup: dict[str, Union[float, str]] = {
        "position_type": position_type,
        "entry": entry,
        "stop_loss": stop,
    }
    if target is not None:
        setup["take_profit"] = target
    return setup


def _extract_labeled_number(text: str, labels: list[str]) -> Optional[float]:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:{label_pattern})\s*[:=\-]?\s*\$?\s*([0-9]+(?:[.,][0-9]+)?)",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _has_period_mismatch(claim: ExtractedNumericClaim, metric_name: str) -> bool:
    if not metric_name.endswith("_ttm"):
        return False
    nearby = claim.nearby_text.lower()
    return claim.period_hint == "mixed" or ("q4" in nearby and "ttm" in nearby)


def _base_metric_name(metric_name: str) -> str:
    return metric_name.removesuffix("_ttm")


def _looks_like_unverified_hard_metric(claim: ExtractedNumericClaim) -> bool:
    return claim.unit in {"usd", "percent", "multiple"} and bool(HARD_METRIC_RE.search(claim.nearby_text))


def _comparable_reported_value(claim: ExtractedNumericClaim, validated_value: float) -> float:
    reported = float(claim.normalized_value or 0)
    if claim.unit == "percent":
        return reported / 100
    return reported


def _numbers_match(reported: float, validated: float, unit: Optional[str]) -> bool:
    if unit == "percent":
        return abs(reported - validated) <= 0.005
    if unit == "multiple":
        return abs(reported - validated) <= max(abs(validated) * 0.01, 0.05)
    return abs(reported - validated) <= max(abs(validated) * 0.01, 1e-6)


def _load_json(path: Optional[Union[str, Path]]) -> dict[str, Any]:
    if path is None:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _model_to_dict(model) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a Markdown stock report against validated packets.")
    parser.add_argument("--report", required=True, help="Path to Markdown report.")
    parser.add_argument("--metrics", required=True, help="Path to metrics_packet.json.")
    parser.add_argument("--validation", help="Path to validation_report.json.")
    parser.add_argument("--sources", help="Path to source_registry.json.")
    parser.add_argument("--evidence", help="Path to evidence_ledger.json.")
    parser.add_argument("--output", help="Optional path to write audit_report.json.")
    args = parser.parse_args(argv)

    audit = audit_report_from_files(
        report_path=args.report,
        metrics_path=args.metrics,
        validation_path=args.validation,
        sources_path=args.sources,
        evidence_path=args.evidence,
    )
    payload = json.dumps(_model_to_dict(audit), indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 2 if audit.has_blocking_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
