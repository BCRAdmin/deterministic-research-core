from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from math import isclose
from typing import Iterable, Optional

from research_agent.reconciliation.canonical_financials import CanonicalFinancials, CanonicalMetric
from research_agent.reconciliation.confidence_scoring import score_confidence
from research_agent.reconciliation.fact_deduplicator import deduplicate_facts
from research_agent.reconciliation.gaap_nongaap_classifier import classify_metric_basis
from research_agent.reconciliation.period_resolver import resolve_period, validate_resolved_period
from research_agent.reconciliation.restatement_resolver import prefer_restatement
from research_agent.reconciliation.unit_normalizer import normalize_value, validate_unit_for_metric
from research_agent.research_core.models.metrics_packet import (
    MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED,
)
from research_agent.sources.sec.companyfacts_parser import ParsedFact
from research_agent.sources.sec.xbrl_concepts import concept_priority


MAX_CURRENT_FINANCIAL_AGE_DAYS = 550
INFORMATIONAL_RECONCILIATION_CODES = {
    "SOURCE_FRAME_VARIANT_IGNORED",
    "PERIOD_TYPE_MISMATCH_IGNORED",
}
LEASE_COMPONENT_CONCEPTS = {
    "lease_liability_current": (
        "us-gaap:OperatingLeaseLiabilityCurrent",
        "us-gaap:FinanceLeaseLiabilityCurrent",
    ),
    "lease_liability_noncurrent": (
        "us-gaap:OperatingLeaseLiabilityNoncurrent",
        "us-gaap:FinanceLeaseLiabilityNoncurrent",
    ),
}


def reconcile_metric(metric_name: str, candidate_metrics: Iterable[CanonicalMetric]):
    candidates = list(candidate_metrics)
    if not candidates:
        return [], []

    warnings: list[dict] = []
    ignored_variant_count = _ignored_variant_count(candidates)
    if ignored_variant_count:
        warnings.append(
            {
                "severity": "info",
                "code": "SOURCE_FRAME_VARIANT_IGNORED",
                "metric": metric_name,
                "count": ignored_variant_count,
                "message": f"Ignored {ignored_variant_count} SEC frame/concept variants across distinct periods for {metric_name}.",
            }
        )

    period_mismatch_count = _period_mismatch_count(candidates)
    if period_mismatch_count:
        warnings.append(
            {
                "severity": "info",
                "code": "PERIOD_TYPE_MISMATCH_IGNORED",
                "metric": metric_name,
                "count": period_mismatch_count,
                "message": f"Ignored {period_mismatch_count} annual/quarterly/YTD period-type variants for {metric_name}.",
            }
        )

    by_comparison_key: dict[tuple, list[CanonicalMetric]] = defaultdict(list)
    for metric in candidates:
        by_comparison_key[_comparison_key(metric)].append(metric)

    canonical: list[CanonicalMetric] = []
    for key, metrics in by_comparison_key.items():
        metrics_sorted = sorted(
            metrics,
            key=lambda metric: (
                _confidence_rank(metric.confidence),
                _source_priority(metric.source_ids),
            ),
            reverse=True,
        )
        top = metrics_sorted[0]
        values = {metric.value for metric in metrics}
        if len(values) > 1:
            if top.period_bucket == "ytd":
                warnings.append(
                    {
                        "severity": "info",
                        "code": "PERIOD_TYPE_MISMATCH_IGNORED",
                        "metric": metric_name,
                        "period_type": top.period_bucket,
                        "count": 1,
                        "message": (
                            f"Ignored YTD source disagreement for {metric_name} ({top.period}); "
                            "YTD facts are kept separate and are not used as quarterly/annual canonical metrics."
                        ),
                    }
                )
                top = _with_note(
                    top,
                    "Ignored YTD source disagreement because YTD facts are not merged into quarterly/annual metrics.",
                )
            else:
                warnings.append(
                    {
                        "severity": "warning",
                        "code": "TRUE_SOURCE_VALUE_DISAGREEMENT",
                        "metric": metric_name,
                        "basis": top.basis,
                        "period_type": top.period_bucket,
                        "period": top.period,
                        "fiscal_year": top.fiscal_year,
                        "fiscal_period": top.fiscal_period,
                        "start_date": top.start_date,
                        "end_date": top.end_date,
                        "source_ids": sorted(
                            {
                                source_id
                                for metric in metrics
                                for source_id in metric.source_ids
                            }
                        ),
                        "candidate_values": sorted(values),
                        "message": f"Comparable sources disagree for {metric_name} ({top.basis}, {top.period_bucket}, {top.period}).",
                    }
                )
                top = _with_note(
                    top, "Selected highest-confidence source among disagreeing values."
                )
        canonical.append(top)

    warnings.extend(_guidance_consensus_warnings(metric_name, canonical))
    warnings.extend(_low_confidence_warnings(canonical))
    return canonical, warnings


def quality_relevant_reconciliation_warnings(
    warnings: Iterable[dict],
    normalized_fundamentals: dict,
) -> list[dict]:
    """Keep only warnings that can affect the current analysis quality.

    Informational period/frame separation remains in the reconciliation
    artifacts but is not a manual-review reason.  Dated value conflicts before
    the earliest period used by the current TTM or growth bridges are likewise
    historical context.  Undated conflicts stay fail-closed.
    """

    review_starts = _material_reconciliation_start_dates(normalized_fundamentals)
    bridge_values = _material_bridge_operand_values(normalized_fundamentals)
    global_review_start = min(review_starts.values()) if review_starts else None
    relevant: list[dict] = []
    for warning in warnings:
        code = str(warning.get("code") or "")
        if code in INFORMATIONAL_RECONCILIATION_CODES:
            continue
        if code == "BALANCE_SHEET_DATE_MISMATCH_EXCLUDED":
            metric = str(warning.get("metric") or "")
            replacement_date = str(
                (
                    normalized_fundamentals.get(
                        "reconciliation_material_dates"
                    )
                    or {}
                ).get(metric)
                or ""
            )
            balance_sheet_date = str(warning.get("balance_sheet_date") or "")
            balance = normalized_fundamentals.get("balance_sheet") or {}
            if (
                metric
                and metric in balance
                and replacement_date
                and replacement_date == balance_sheet_date
            ):
                continue
        if code != "TRUE_SOURCE_VALUE_DISAGREEMENT" or not review_starts:
            relevant.append(warning)
            continue
        end_date = _valid_iso_date(warning.get("end_date"))
        metric = str(warning.get("metric") or "")
        if end_date is None:
            relevant.append(warning)
            continue
        if not metric:
            if global_review_start is not None and end_date >= global_review_start:
                relevant.append(warning)
            continue
        candidate_values = warning.get("candidate_values")
        material_values = bridge_values.get(metric)
        if isinstance(candidate_values, list) and material_values:
            comparable_candidates = [
                float(value)
                for value in candidate_values
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            ]
            if any(
                isclose(candidate, material, rel_tol=1e-9, abs_tol=1e-6)
                for candidate in comparable_candidates
                for material in material_values
            ):
                relevant.append(warning)
            continue
        review_start = review_starts.get(metric)
        if review_start is not None and end_date >= review_start:
            relevant.append(warning)
    return relevant


def _material_bridge_operand_values(
    normalized_fundamentals: dict,
) -> dict[str, list[float]]:
    values: dict[str, list[float]] = defaultdict(list)

    def record(metric: object, bridge: object) -> None:
        metric_name = str(metric or "")
        if not metric_name or not isinstance(bridge, dict):
            return
        operands = bridge.get("operands")
        if not isinstance(operands, dict):
            return
        values[metric_name].extend(
            float(value)
            for value in operands.values()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        )

    bridges = normalized_fundamentals.get("ttm_bridges")
    if isinstance(bridges, dict):
        for metric, bridge in bridges.items():
            record(metric, bridge)

    record("revenue", normalized_fundamentals.get("revenue_growth_yoy_bridge"))

    current_growth_bridges = normalized_fundamentals.get(
        "current_period_growth_bridges"
    )
    if isinstance(current_growth_bridges, dict):
        for metric, bridge in current_growth_bridges.items():
            record(metric, bridge)
    return dict(values)


def _material_reconciliation_start_date(
    normalized_fundamentals: dict,
) -> Optional[date]:
    starts = _material_reconciliation_start_dates(normalized_fundamentals)
    return min(starts.values()) if starts else None


def _material_reconciliation_start_dates(
    normalized_fundamentals: dict,
) -> dict[str, date]:
    starts: dict[str, date] = {}

    def record(metric: object, value: object) -> None:
        metric_name = str(metric or "")
        parsed = _valid_iso_date(value)
        if not metric_name or parsed is None:
            return
        existing = starts.get(metric_name)
        if existing is None or parsed < existing:
            starts[metric_name] = parsed

    explicit_dates = normalized_fundamentals.get("reconciliation_material_dates")
    if isinstance(explicit_dates, dict):
        for metric, value in explicit_dates.items():
            record(metric, value)

    bridges = normalized_fundamentals.get("ttm_bridges")
    if isinstance(bridges, dict):
        for metric, bridge in bridges.items():
            if isinstance(bridge, dict):
                record(metric, bridge.get("period_start"))

    growth_bridge = normalized_fundamentals.get("revenue_growth_yoy_bridge")
    if isinstance(growth_bridge, dict):
        record("revenue", growth_bridge.get("period_start"))

    current_growth_bridges = normalized_fundamentals.get(
        "current_period_growth_bridges"
    )
    if isinstance(current_growth_bridges, dict):
        for metric, bridge in current_growth_bridges.items():
            if isinstance(bridge, dict):
                record(metric, bridge.get("period_start"))
    return starts


def _valid_iso_date(value: object) -> Optional[date]:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def canonical_metric_from_parsed_fact(
    ticker: str,
    fact: ParsedFact,
    evidence_id: Optional[str] = None,
    source_text: Optional[str] = None,
) -> tuple[Optional[CanonicalMetric], list[dict]]:
    warnings: list[dict] = []
    resolved = resolve_period(fact.metric_name, fact)
    warnings.extend(validate_resolved_period(fact.metric_name, resolved))
    value, unit = normalize_value(fact.value, fact.unit)
    unit_issue = validate_unit_for_metric(fact.metric_name, unit)
    if unit_issue:
        warnings.append(unit_issue)

    source_id = f"SEC_{str(getattr(fact, 'accession', None) or getattr(fact, 'filed', 'unknown'))}"
    basis = classify_metric_basis(fact.source_type, fact.metric_name, source_text)
    confidence = score_confidence(
        source_rank=1,
        has_period=bool(resolved.period_label and resolved.period_label != "unknown"),
        has_unit=bool(unit),
        is_reconciled=True,
    )
    resolved_evidence_id = evidence_id or getattr(fact, "evidence_id", None)
    canonical = CanonicalMetric(
        metric_name=fact.metric_name,
        value=value,
        unit=unit,
        period=resolved.period_label,
        fiscal_year=resolved.fiscal_year,
        fiscal_period=resolved.fiscal_period,
        period_bucket=resolved.period_bucket,
        start_date=resolved.start_date,
        end_date=resolved.end_date,
        duration_days=resolved.duration_days,
        frame=resolved.frame,
        source_concept=getattr(fact, "concept", None),
        basis=basis,
        statement_type=_statement_type(fact.metric_name),
        source_ids=[source_id],
        evidence_ids=[resolved_evidence_id] if resolved_evidence_id else [],
        confidence=confidence,
        reconciliation_notes=[
            f"Resolved as {resolved.period_type}/{resolved.period_bucket} period {resolved.period_label}.",
            *([fact.normalization_note] if getattr(fact, "normalization_note", None) else []),
        ],
    )
    if getattr(fact, "normalization_note", None):
        warnings.append(
            {
                "severity": "info",
                "code": "SEC_SHARE_SCALE_NORMALIZED",
                "metric": fact.metric_name,
                "raw_value": fact.raw_value,
                "normalized_value": fact.value,
                "message": fact.normalization_note,
            }
        )
    return canonical, warnings


def build_canonical_financials_from_facts(
    ticker: str,
    as_of_date: str,
    facts: Iterable[ParsedFact],
) -> tuple[CanonicalFinancials, list[dict]]:
    facts = list(facts)
    restated = prefer_restatement(facts)
    deduped, warnings = deduplicate_facts(restated)
    candidates_by_metric: dict[str, list[CanonicalMetric]] = defaultdict(list)

    for fact in deduped:
        canonical, metric_warnings = canonical_metric_from_parsed_fact(ticker, fact)
        warnings.extend(metric_warnings)
        if canonical:
            candidates_by_metric[fact.metric_name].append(canonical)

    canonical_metrics: list[CanonicalMetric] = []
    for metric_name, candidates in candidates_by_metric.items():
        reconciled, metric_warnings = reconcile_metric(metric_name, candidates)
        warnings.extend(metric_warnings)
        canonical_metrics.extend(reconciled)

    return (
        CanonicalFinancials(
            ticker=ticker.upper(),
            as_of_date=as_of_date,
            metrics=canonical_metrics,
        ),
        _coalesce_share_scale_warnings(warnings),
    )


def _coalesce_share_scale_warnings(warnings: list[dict]) -> list[dict]:
    share_scale = [
        warning for warning in warnings if warning.get("code") == "SEC_SHARE_SCALE_NORMALIZED"
    ]
    if len(share_scale) <= 1:
        return warnings

    others = [
        warning for warning in warnings if warning.get("code") != "SEC_SHARE_SCALE_NORMALIZED"
    ]
    latest = share_scale[-1]
    others.append(
        {
            "severity": "info",
            "code": "SEC_SHARE_SCALE_NORMALIZED",
            "metric": "shares_diluted",
            "count": len(share_scale),
            "latest_raw_value": latest.get("raw_value"),
            "latest_normalized_value": latest.get("normalized_value"),
            "message": (
                f"Normalized {len(share_scale)} SEC diluted-share observations "
                "with a consistent power-of-ten scale reconciled against "
                "same-period net income and diluted EPS."
            ),
        }
    )
    return others


def canonical_financials_to_fundamentals(canonical: CanonicalFinancials) -> dict:
    fundamentals = {
        "quarterly": {},
        "ttm": {},
        "annual": {},
        "balance_sheet": {},
        "share_data": {},
        "reconciliation_material_dates": {},
        "source": "canonical_financials",
        "reconciliation_issues": [],
    }
    duration_metrics = {
        "revenue",
        "gross_profit",
        "operating_income",
        "ebitda",
        "net_income",
        "operating_cash_flow",
        "capex",
        "sbc",
        "buybacks",
        "dividends_paid",
        "depreciation_and_amortization",
        "interest_expense",
        "eps_diluted",
    }
    for metric_name in duration_metrics:
        values, issue, bridge = _compatible_trailing_period_values(canonical, metric_name)
        if values:
            if len(values) == 4:
                fundamentals["quarterly"][metric_name] = values
            elif bridge:
                fundamentals["ttm"][metric_name] = sum(values)
            if bridge:
                fundamentals.setdefault("ttm_bridges", {})[metric_name] = bridge
        else:
            annual = _latest_annual_metric(canonical, metric_name)
            if annual is not None:
                fundamentals["annual"][metric_name] = annual.value
                fundamentals["reconciliation_material_dates"][metric_name] = (
                    annual.start_date
                )
            if issue:
                fundamentals["reconciliation_issues"].append(issue)

    balance_sheet_metrics = {
        "cash_and_equivalents",
        "short_term_investments",
        "current_assets",
        "current_liabilities",
        "equity",
        "total_debt",
        "short_term_debt",
        "debt_current",
        "debt_noncurrent",
        "lease_liability_current",
        "lease_liability_noncurrent",
        "treasury_stock_value",
    }
    balance_sheet_date = _latest_balance_sheet_date(canonical)
    for metric_name in balance_sheet_metrics:
        selected = _latest_current_metric(canonical, metric_name, require_gaap=True)
        if selected is not None:
            if balance_sheet_date and selected.end_date != balance_sheet_date:
                fundamentals["reconciliation_issues"].append(
                    {
                        "severity": "warning",
                        "code": "BALANCE_SHEET_DATE_MISMATCH_EXCLUDED",
                        "metric": metric_name,
                        "metric_end_date": selected.end_date,
                        "balance_sheet_date": balance_sheet_date,
                        "message": (
                            f"Excluded {metric_name} from {selected.end_date} because "
                            f"the latest financial-statement balance date is {balance_sheet_date}."
                        ),
                    }
                )
                continue
            fundamentals["balance_sheet"][metric_name] = selected.value
            fundamentals["reconciliation_material_dates"][metric_name] = (
                selected.end_date
            )
        elif canonical.metrics_for(metric_name):
            fundamentals["reconciliation_issues"].append(_stale_metric_issue(metric_name))

    _derive_debt_and_lease_totals(
        canonical,
        fundamentals,
        balance_sheet_date=balance_sheet_date,
    )
    _derive_revenue_growth(canonical, fundamentals)
    _derive_current_period_growth(canonical, fundamentals)
    _derive_fiscal_context(canonical, fundamentals)

    share_metrics = {
        "shares_diluted": "diluted_share_count",
        "listed_share_count": "listed_share_count",
        "treasury_share_count": "treasury_share_count",
        "economic_share_count": "economic_share_count",
    }
    for metric_name, output_name in share_metrics.items():
        selected = _latest_current_metric(
            canonical,
            metric_name,
            require_gaap=metric_name == "shares_diluted",
        )
        if selected is not None:
            fundamentals["share_data"][output_name] = selected.value
            fundamentals["reconciliation_material_dates"][metric_name] = (
                selected.end_date
            )
            if metric_name == "economic_share_count" and any(
                "[MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED]" in note
                for note in selected.reconciliation_notes
            ):
                fundamentals["share_data"]["economic_share_count_basis"] = (
                    MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED
                )
                fundamentals["reconciliation_issues"].append(
                    {
                        "severity": "warning",
                        "code": "MULTI_CLASS_PRICE_BASIS_UNAVAILABLE",
                        "metric": "market_cap",
                        "message": (
                            "The filed cover page reports multiple stock classes, "
                            "but the current packet has only one traded-class price "
                            "and no evidence that this price can be applied across "
                            "all classes. Market-cap-derived valuation is unavailable."
                        ),
                    }
                )
        elif canonical.metrics_for(metric_name):
            fundamentals["reconciliation_issues"].append(_stale_metric_issue(metric_name))
    _derive_diluted_share_count_yoy(canonical, fundamentals)
    return fundamentals


def _compatible_trailing_period_values(
    canonical: CanonicalFinancials, metric_name: str
) -> tuple[list[float], Optional[dict], Optional[dict]]:
    quarterly = _dedupe_period_metrics(
        [
            metric
            for metric in canonical.metrics_for(metric_name)
            if metric.period_bucket == "quarterly"
            and metric.basis == "gaap"
            and _is_current_metric(canonical, metric)
            and metric.start_date
            and metric.end_date
            and metric.duration_days is not None
            and 70 <= metric.duration_days <= 110
        ]
    )
    if len(quarterly) >= 4 and _quarters_are_contiguous(quarterly[-4:]):
        selected = quarterly[-4:]
        return (
            [metric.value for metric in selected],
            None,
            {
                "formula_id": "sum_four_contiguous_quarters",
                "operands": {
                    metric.period: metric.value
                    for metric in selected
                },
                "period_start": selected[0].start_date,
                "period_end": selected[-1].end_date,
                "source_ids": sorted(
                    {
                        source_id
                        for metric in selected
                        for source_id in metric.source_ids
                    }
                ),
            },
        )

    annual = _latest_annual_metric(canonical, metric_name)
    if annual is not None:
        interim_bridge = _derive_ttm_from_matching_interims(
            canonical,
            metric_name,
            annual,
        )
        if interim_bridge is not None:
            values, bridge = interim_bridge
            return values, None, bridge
        derived = _derive_q4_and_trailing_values(annual, quarterly)
        if derived is not None:
            values, bridge = derived
            return values, None, bridge

    available = canonical.metrics_for(metric_name)
    if available and not any(_is_current_metric(canonical, metric) for metric in available):
        return [], _stale_metric_issue(metric_name), None
    return [], {
        "severity": "warning",
        "code": "MISSING_COMPATIBLE_DENOMINATOR"
        if metric_name == "revenue"
        else "MISSING_COMPATIBLE_NUMERATOR",
        "metric": metric_name,
        "message": f"Could not build four compatible quarterly periods for {metric_name}; ratio inputs should use annual fallback or remain unavailable.",
    }, None


def _dedupe_period_metrics(metrics: list[CanonicalMetric]) -> list[CanonicalMetric]:
    by_dates: dict[tuple[str, str], CanonicalMetric] = {}
    for metric in sorted(
        metrics,
        key=lambda item: (
            item.end_date or "",
            _confidence_rank(item.confidence),
            concept_priority(item.metric_name, item.source_concept),
            1 if item.frame else 0,
        ),
    ):
        if not metric.start_date or not metric.end_date:
            continue
        key = (metric.start_date, metric.end_date)
        existing = by_dates.get(key)
        if existing is None or _confidence_rank(metric.confidence) >= _confidence_rank(
            existing.confidence
        ):
            by_dates[key] = metric
    return sorted(by_dates.values(), key=lambda item: item.end_date or "")


def _latest_annual_metric(
    canonical: CanonicalFinancials, metric_name: str
) -> Optional[CanonicalMetric]:
    annual = [
        metric
        for metric in canonical.metrics_for(metric_name)
        if metric.period_bucket == "annual"
        and metric.basis == "gaap"
        and _is_current_metric(canonical, metric)
        and metric.start_date
        and metric.end_date
    ]
    if not annual:
        return None
    return sorted(
        annual,
        key=lambda metric: (
            metric.end_date or "",
            _confidence_rank(metric.confidence),
            concept_priority(metric.metric_name, metric.source_concept),
            1 if metric.frame else 0,
        ),
        reverse=True,
    )[0]


def _latest_current_metric(
    canonical: CanonicalFinancials,
    metric_name: str,
    *,
    require_gaap: bool,
) -> Optional[CanonicalMetric]:
    candidates = [
        metric
        for metric in canonical.metrics_for(metric_name)
        if (not require_gaap or metric.basis == "gaap") and _is_current_metric(canonical, metric)
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda metric: (
            metric.end_date or "",
            _confidence_rank(metric.confidence),
            concept_priority(metric.metric_name, metric.source_concept),
            1 if metric.frame else 0,
        ),
        reverse=True,
    )[0]


def _distinct_lease_component_bridge(
    canonical: CanonicalFinancials,
    metric_name: str,
    *,
    balance_sheet_date: Optional[str],
) -> Optional[tuple[float, dict]]:
    concepts = LEASE_COMPONENT_CONCEPTS.get(metric_name, ())
    selected: list[CanonicalMetric] = []
    for concept in concepts:
        candidates = [
            metric
            for metric in canonical.metrics_for(metric_name)
            if metric.basis == "gaap"
            and metric.source_concept == concept
            and _is_current_metric(canonical, metric)
            and (
                not balance_sheet_date
                or metric.end_date == balance_sheet_date
            )
        ]
        if not candidates:
            continue
        selected.append(
            sorted(
                candidates,
                key=lambda metric: (
                    metric.end_date or "",
                    _confidence_rank(metric.confidence),
                    1 if metric.frame else 0,
                ),
                reverse=True,
            )[0]
        )
    if len(selected) != len(concepts):
        return None
    operand_suffix = (
        "current" if metric_name.endswith("_current") else "noncurrent"
    )
    operands = {
        f"operating_lease_liability_{operand_suffix}": selected[0].value,
        f"finance_lease_liability_{operand_suffix}": selected[1].value,
    }
    return sum(operands.values()), {
        "formula_id": "sum_distinct_lease_liability_concepts",
        "operands": operands,
        "period_end": selected[0].end_date,
        "source_ids": sorted(
            {
                source_id
                for metric in selected
                for source_id in metric.source_ids
            }
        ),
    }


def _is_current_metric(
    canonical: CanonicalFinancials,
    metric: CanonicalMetric,
) -> bool:
    if not metric.end_date:
        return False
    try:
        as_of = date.fromisoformat(canonical.as_of_date)
        metric_end = date.fromisoformat(metric.end_date)
    except ValueError:
        return False
    age_days = (as_of - metric_end).days
    return 0 <= age_days <= MAX_CURRENT_FINANCIAL_AGE_DAYS


def _stale_metric_issue(metric_name: str) -> dict:
    return {
        "severity": "warning",
        "code": "STALE_FINANCIAL_METRIC_EXCLUDED",
        "metric": metric_name,
        "message": (
            f"Excluded {metric_name} because no observation falls within "
            f"{MAX_CURRENT_FINANCIAL_AGE_DAYS} days of the analysis date."
        ),
    }


def _derive_q4_and_trailing_values(
    annual: CanonicalMetric, quarterly: list[CanonicalMetric]
) -> Optional[tuple[list[float], dict]]:
    annual_quarters = [
        metric
        for metric in quarterly
        if metric.start_date
        and metric.end_date
        and annual.start_date
        and annual.end_date
        and annual.start_date <= metric.start_date
        and metric.end_date <= annual.end_date
    ]
    annual_quarters = _dedupe_period_metrics(annual_quarters)
    if len(annual_quarters) < 3:
        return None
    first_three = annual_quarters[:3]
    q4_value = annual.value - sum(metric.value for metric in first_three)
    if q4_value < 0:
        return None
    annual_end = annual.end_date or ""
    trailing_after_annual = [
        metric for metric in quarterly if metric.start_date and metric.start_date > annual_end
    ]
    values = [metric.value for metric in first_three[-3:]] + [q4_value]
    bridge = {
        "formula_id": "annual_minus_q1_q2_q3_plus_post_annual_quarters",
        "operands": {
            "annual": annual.value,
            **{
                metric.period: metric.value
                for metric in first_three[-3:]
            },
            "derived_q4": q4_value,
        },
        "period_start": first_three[0].start_date,
        "period_end": annual.end_date,
        "source_ids": sorted(
            {
                source_id
                for metric in [annual, *first_three]
                for source_id in metric.source_ids
            }
        ),
    }
    if trailing_after_annual:
        combined = values + [metric.value for metric in trailing_after_annual]
        selected = combined[-4:]
        post_annual_quarter_count = min(len(trailing_after_annual), 3)
        bridge["formula_id"] = "annual_minus_prior_interim_plus_current_interim"
        bridge["operands"] = {
            "annual": annual.value,
            "prior_interim": sum(
                metric.value
                for metric in first_three[:post_annual_quarter_count]
            ),
            "current_interim": sum(
                metric.value for metric in trailing_after_annual
            ),
        }
        bridge["period_end"] = trailing_after_annual[-1].end_date
        bridge["source_ids"] = sorted(
            set(bridge["source_ids"])
            | {
                source_id
                for metric in trailing_after_annual
                for source_id in metric.source_ids
            }
        )
        return selected, bridge
    return values[-4:], bridge


def _derive_ttm_from_matching_interims(
    canonical: CanonicalFinancials,
    metric_name: str,
    annual: CanonicalMetric,
) -> Optional[tuple[list[float], dict]]:
    if annual.fiscal_year is None:
        return None
    interims = [
        metric
        for metric in canonical.metrics_for(metric_name)
        if metric.basis == "gaap"
        and metric.period_bucket in {"quarterly", "ytd"}
        and metric.fiscal_year is not None
        and metric.fiscal_period in {"Q1", "Q2", "Q3"}
        and metric.start_date
        and metric.end_date
        and _is_valid_interim_duration(metric)
        and _is_current_metric(canonical, metric)
    ]
    current_candidates = [
        metric
        for metric in interims
        if metric.fiscal_year == annual.fiscal_year + 1
        and (metric.start_date or "") > (annual.end_date or "")
    ]
    if not current_candidates:
        return None
    current = max(
        current_candidates,
        key=lambda metric: (metric.end_date or "", metric.duration_days or 0),
    )
    prior_candidates = [
        metric
        for metric in interims
        if metric.fiscal_year == annual.fiscal_year
        and metric.fiscal_period == current.fiscal_period
        and (metric.end_date or "") <= (annual.end_date or "")
        and abs((metric.duration_days or 0) - (current.duration_days or 0)) <= 7
    ]
    if not prior_candidates:
        return None
    prior = max(
        prior_candidates,
        key=lambda metric: (metric.end_date or "", metric.duration_days or 0),
    )
    trailing_prior = annual.value - prior.value
    return (
        [trailing_prior, current.value],
        {
            "formula_id": "annual_minus_prior_interim_plus_current_interim",
            "operands": {
                "annual": annual.value,
                "prior_interim": prior.value,
                "current_interim": current.value,
            },
            "period_start": (
                date.fromisoformat(prior.end_date) + timedelta(days=1)
            ).isoformat(),
            "period_end": current.end_date,
            "source_ids": sorted(
                {
                    *annual.source_ids,
                    *prior.source_ids,
                    *current.source_ids,
                }
            ),
        },
    )


def _is_valid_interim_duration(metric: CanonicalMetric) -> bool:
    duration = metric.duration_days
    if duration is None:
        return False
    expected_ranges = {
        "Q1": (70, 110),
        "Q2": (150, 210),
        "Q3": (230, 310),
    }
    lower, upper = expected_ranges[metric.fiscal_period]
    return lower <= duration <= upper


def _quarters_are_contiguous(metrics: list[CanonicalMetric]) -> bool:
    if len(metrics) != 4:
        return False
    try:
        starts = [date.fromisoformat(metric.start_date or "") for metric in metrics]
        ends = [date.fromisoformat(metric.end_date or "") for metric in metrics]
    except ValueError:
        return False
    return all(
        0 <= (starts[index] - ends[index - 1]).days <= 4
        for index in range(1, len(metrics))
    )


def _derive_debt_and_lease_totals(
    canonical: CanonicalFinancials,
    fundamentals: dict,
    *,
    balance_sheet_date: Optional[str],
) -> None:
    balance = fundamentals["balance_sheet"]
    aggregate = _latest_current_metric(
        canonical, "total_debt", require_gaap=True
    )
    short_term = _latest_current_metric(
        canonical, "short_term_debt", require_gaap=True
    )
    current = _latest_current_metric(
        canonical, "debt_current", require_gaap=True
    )
    noncurrent = _latest_current_metric(
        canonical, "debt_noncurrent", require_gaap=True
    )
    if balance_sheet_date:
        aggregate = (
            aggregate if aggregate and aggregate.end_date == balance_sheet_date else None
        )
        short_term = (
            short_term if short_term and short_term.end_date == balance_sheet_date else None
        )
        current = current if current and current.end_date == balance_sheet_date else None
        noncurrent = (
            noncurrent if noncurrent and noncurrent.end_date == balance_sheet_date else None
        )
    component_end_dates = [
        metric.end_date
        for metric in (short_term, current, noncurrent)
        if metric is not None
    ]
    latest_component_date = max(component_end_dates) if component_end_dates else None
    if noncurrent is not None:
        component_values = {"debt_noncurrent": noncurrent.value}
        if current is not None and current.end_date == noncurrent.end_date:
            component_values["debt_current"] = current.value
        current_is_aggregate = (
            current is not None
            and current.end_date == noncurrent.end_date
            and current.source_concept == "us-gaap:DebtCurrent"
        )
        if (
            short_term is not None
            and short_term.end_date == noncurrent.end_date
            and not current_is_aggregate
            and not _duplicate_debt_component(current, short_term)
        ):
            component_values["short_term_debt"] = short_term.value
        elif _duplicate_debt_component(current, short_term):
            balance.pop("short_term_debt", None)
        use_components = (
            aggregate is None
            or (
                latest_component_date is not None
                and (aggregate.end_date or "") < latest_component_date
            )
            or (
                len(component_values) > 1
                and latest_component_date is not None
                and (aggregate.end_date or "") == latest_component_date
            )
        )
        if use_components:
            balance["total_debt"] = sum(component_values.values())
            fundamentals["reconciliation_material_dates"]["total_debt"] = (
                noncurrent.end_date
            )
            balance["debt_noncurrent"] = noncurrent.value
            if "debt_current" in component_values:
                balance["debt_current"] = component_values["debt_current"]
            if "short_term_debt" in component_values:
                balance["short_term_debt"] = component_values["short_term_debt"]
    if (
        noncurrent is not None
        and current is not None
        and current.end_date != noncurrent.end_date
    ):
        balance.pop("debt_current", None)

    for metric_name in LEASE_COMPONENT_CONCEPTS:
        bridge_result = _distinct_lease_component_bridge(
            canonical,
            metric_name,
            balance_sheet_date=balance_sheet_date,
        )
        if bridge_result is None:
            continue
        value, bridge = bridge_result
        balance[metric_name] = value
        fundamentals.setdefault("lease_component_bridges", {})[
            metric_name
        ] = bridge
        fundamentals["reconciliation_material_dates"][metric_name] = (
            bridge["period_end"]
        )

    lease_current = balance.get("lease_liability_current")
    lease_noncurrent = balance.get("lease_liability_noncurrent")
    if lease_current is not None and lease_noncurrent is not None:
        balance["total_lease_liabilities"] = (
            float(lease_current) + float(lease_noncurrent)
        )
        if balance_sheet_date:
            fundamentals["reconciliation_material_dates"][
                "total_lease_liabilities"
            ] = balance_sheet_date
    else:
        balance.pop("total_lease_liabilities", None)
        fundamentals["reconciliation_material_dates"].pop(
            "total_lease_liabilities",
            None,
        )


def _duplicate_debt_component(
    current: Optional[CanonicalMetric],
    short_term: Optional[CanonicalMetric],
) -> bool:
    if (
        current is None
        or short_term is None
        or current.end_date != short_term.end_date
        or not set(current.source_ids).intersection(short_term.source_ids)
        or current.source_concept
        not in {
            "us-gaap:LongTermDebtCurrent",
            "us-gaap:LongTermDebtAndCapitalLeaseObligationsCurrent",
        }
        or short_term.source_concept
        not in {
            "us-gaap:ShortTermBorrowings",
            "us-gaap:CommercialPaper",
        }
    ):
        return False
    scale = max(abs(current.value), abs(short_term.value))
    if scale == 0:
        return True
    return abs(current.value - short_term.value) / scale <= 0.001


def _latest_balance_sheet_date(canonical: CanonicalFinancials) -> Optional[str]:
    statement_dates = [
        metric.end_date
        for metric in canonical.metrics
        if metric.statement_type == "balance_sheet"
        and metric.metric_name
        not in {
            "economic_share_count",
            "listed_share_count",
            "treasury_share_count",
        }
        and metric.end_date
        and _is_current_metric(canonical, metric)
    ]
    return max(statement_dates) if statement_dates else None


def _derive_revenue_growth(
    canonical: CanonicalFinancials,
    fundamentals: dict,
) -> None:
    annual = sorted(
        _dedupe_period_metrics(
            [
                metric
                for metric in canonical.metrics_for("revenue")
                if metric.period_bucket == "annual"
                and metric.basis == "gaap"
                and metric.start_date
                and metric.end_date
            ]
        ),
        key=lambda metric: metric.end_date or "",
    )
    if len(annual) < 2 or annual[-2].value == 0:
        return
    current = annual[-1]
    prior = annual[-2]
    if not _is_current_metric(canonical, current):
        return
    fundamentals["revenue_growth_yoy"] = (
        current.value - prior.value
    ) / prior.value
    fundamentals["revenue_growth_yoy_bridge"] = {
        "formula_id": "annual_revenue_yoy_growth",
        "operands": {
            "current_annual_revenue": current.value,
            "prior_annual_revenue": prior.value,
        },
        "period_start": prior.start_date,
        "period_end": current.end_date,
        "source_ids": sorted(
            {
                *current.source_ids,
                *prior.source_ids,
            }
        ),
    }


def _derive_current_period_growth(
    canonical: CanonicalFinancials,
    fundamentals: dict,
) -> None:
    bridges: dict[str, dict] = {}
    for metric_name in ("revenue", "operating_income", "net_income"):
        reported = _dedupe_period_metrics(
            [
                metric
                for metric in canonical.metrics_for(metric_name)
                if metric.period_bucket in {"annual", "quarterly"}
                and metric.basis == "gaap"
                and metric.fiscal_year is not None
                and metric.fiscal_period
                and metric.start_date
                and metric.end_date
                and metric.duration_days is not None
                and (
                    70 <= metric.duration_days <= 110
                    if metric.period_bucket == "quarterly"
                    else 330 <= metric.duration_days <= 400
                )
                and _is_current_metric(canonical, metric)
            ]
        )
        if not reported:
            continue
        current = max(
            reported,
            key=lambda metric: (
                metric.end_date or "",
                1 if metric.period_bucket == "annual" else 0,
            ),
        )
        current_end = _valid_iso_date(current.end_date)
        if current_end is None:
            continue
        prior_candidates = [
            metric
            for metric in reported
            if metric.period_bucket == current.period_bucket
            if metric.fiscal_period == current.fiscal_period
            and metric.end_date < current.end_date
            and abs((metric.duration_days or 0) - (current.duration_days or 0)) <= 7
            and (
                (prior_end := _valid_iso_date(metric.end_date)) is not None
                and 330 <= (current_end - prior_end).days <= 400
            )
        ]
        if not prior_candidates:
            continue
        prior = prior_candidates[-1]
        if prior.value <= 0:
            continue
        growth = (current.value - prior.value) / prior.value
        output_name = f"current_period_{metric_name}_growth_yoy"
        fundamentals[output_name] = growth
        bridges[metric_name] = {
            "formula_id": (
                "matching_fiscal_year_yoy_growth"
                if current.period_bucket == "annual"
                else "matching_quarter_yoy_growth"
            ),
            "operands": {
                f"current_{metric_name}": current.value,
                f"prior_{metric_name}": prior.value,
            },
            "period_type": current.period_bucket,
            "current_period": current.period,
            "prior_period": prior.period,
            "period_start": prior.start_date,
            "period_end": current.end_date,
            "source_ids": sorted({*current.source_ids, *prior.source_ids}),
        }
    if bridges:
        fundamentals["current_period_growth_bridges"] = bridges


def _derive_diluted_share_count_yoy(
    canonical: CanonicalFinancials,
    fundamentals: dict,
) -> None:
    current = _latest_current_metric(
        canonical,
        "shares_diluted",
        require_gaap=True,
    )
    if (
        current is None
        or current.period_bucket not in {"annual", "quarterly"}
        or not current.fiscal_period
        or not current.start_date
        or not current.end_date
        or current.duration_days is None
    ):
        return
    current_end = _valid_iso_date(current.end_date)
    if current_end is None:
        return
    prior_candidates = _dedupe_period_metrics(
        [
            metric
            for metric in canonical.metrics_for("shares_diluted")
            if metric.basis == "gaap"
            and metric.period_bucket == current.period_bucket
            and metric.fiscal_period == current.fiscal_period
            and metric.start_date
            and metric.end_date
            and metric.duration_days is not None
            and metric.end_date < current.end_date
            and abs(metric.duration_days - current.duration_days) <= 7
            and (
                (prior_end := _valid_iso_date(metric.end_date)) is not None
                and 330 <= (current_end - prior_end).days <= 400
            )
            and _is_current_metric(canonical, metric)
        ]
    )
    if not prior_candidates:
        return
    prior = prior_candidates[-1]
    if prior.value <= 0:
        return
    fundamentals["share_data"]["diluted_share_count_prior_year"] = prior.value
    fundamentals["diluted_share_count_yoy_bridge"] = {
        "formula_id": "matching_period_diluted_share_count_yoy_change",
        "operands": {
            "current_diluted_share_count": current.value,
            "prior_diluted_share_count": prior.value,
        },
        "current_period": current.period,
        "prior_period": prior.period,
        "period_start": prior.start_date,
        "period_end": current.end_date,
        "source_ids": sorted({*current.source_ids, *prior.source_ids}),
    }


def _derive_fiscal_context(
    canonical: CanonicalFinancials,
    fundamentals: dict,
) -> None:
    annual = sorted(
        [
            metric
            for metric in canonical.metrics
            if metric.metric_name == "revenue"
            and metric.period_bucket == "annual"
            and metric.end_date
            and metric.fiscal_year is not None
            and _is_current_metric(canonical, metric)
        ],
        key=lambda metric: metric.end_date or "",
    )
    if annual:
        latest_annual = annual[-1]
        fundamentals["latest_fiscal_year"] = f"FY{latest_annual.fiscal_year}"
        fundamentals["fiscal_year_end"] = latest_annual.end_date[5:10]

    quarterly = sorted(
        [
            metric
            for metric in canonical.metrics
            if metric.period_bucket == "quarterly"
            and metric.end_date
            and _is_current_metric(canonical, metric)
        ],
        key=lambda metric: metric.end_date or "",
    )
    if not quarterly and not annual:
        return
    if quarterly:
        latest_quarter = quarterly[-1]
        if latest_quarter.fiscal_year and latest_quarter.fiscal_period:
            fundamentals["latest_quarter"] = (
                f"FY{latest_quarter.fiscal_year}_{latest_quarter.fiscal_period}"
            )
    latest = max(
        [*annual, *quarterly],
        key=lambda metric: (
            metric.end_date or "",
            1 if metric.period_bucket == "annual" else 0,
        ),
    )
    if latest.fiscal_year and latest.fiscal_period:
        period_label = (
            f"FY{latest.fiscal_year}"
            if latest.fiscal_period == "FY"
            else f"FY{latest.fiscal_year}_{latest.fiscal_period}"
        )
        fundamentals["fiscal_period"] = f"TTM through {period_label}"
    else:
        fundamentals["fiscal_period"] = f"TTM through {latest.end_date}"


def _guidance_consensus_warnings(metric_name: str, metrics: list[CanonicalMetric]) -> list[dict]:
    if metric_name not in {"forward_eps", "eps", "company_guidance_eps", "consensus_forward_eps"}:
        return []
    guidance = [metric for metric in metrics if metric.basis in {"company_defined", "non_gaap"}]
    consensus = [metric for metric in metrics if metric.basis == "consensus"]
    warnings = []
    for guidance_metric in guidance:
        for consensus_metric in consensus:
            if guidance_metric.value == 0:
                continue
            diff = abs(consensus_metric.value - guidance_metric.value) / abs(guidance_metric.value)
            if diff > 0.10:
                warnings.append(
                    {
                        "severity": "warning",
                        "code": "CONSENSUS_GUIDANCE_MISMATCH",
                        "metric": metric_name,
                        "message": f"Consensus and company guidance differ by {diff:.1%}.",
                    }
                )
    return warnings


def _low_confidence_warnings(metrics: list[CanonicalMetric]) -> list[dict]:
    return [
        {
            "severity": "warning",
            "code": "LOW_CONFIDENCE_CANONICAL_METRIC",
            "metric": metric.metric_name,
            "message": f"{metric.metric_name} canonical metric confidence is low.",
        }
        for metric in metrics
        if metric.confidence == "low"
    ]


def _statement_type(metric_name: str):
    if metric_name in {"revenue", "gross_profit", "operating_income", "net_income", "eps_diluted"}:
        return "income_statement"
    if metric_name in {
        "operating_cash_flow",
        "capex",
        "sbc",
        "buybacks",
        "dividends_paid",
        "depreciation_and_amortization",
        "interest_expense",
    }:
        return "cash_flow"
    if metric_name in {
        "cash_and_equivalents",
        "short_term_investments",
        "total_assets",
        "total_liabilities",
        "stockholders_equity",
        "total_debt",
        "short_term_debt",
        "debt_current",
        "debt_noncurrent",
        "lease_liability_current",
        "lease_liability_noncurrent",
        "treasury_stock_value",
        "treasury_share_count",
        "listed_share_count",
        "economic_share_count",
    }:
        return "balance_sheet"
    if "guidance" in metric_name:
        return "guidance"
    return "income_statement"


def _confidence_rank(confidence: str) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(confidence, 0)


def _source_priority(source_ids: list[str]) -> int:
    joined = " ".join(source_ids).upper()
    if "SEC" in joined:
        return 5
    if "IR" in joined:
        return 4
    return 1


def _comparison_key(metric: CanonicalMetric) -> tuple:
    if metric.frame:
        period_identity = ("frame", metric.frame)
    else:
        period_identity = ("dates", metric.start_date, metric.end_date)
    return (
        metric.metric_name,
        metric.basis,
        metric.unit,
        metric.period_bucket,
        period_identity,
        metric.source_concept,
    )


def _ignored_variant_count(metrics: list[CanonicalMetric]) -> int:
    count = 0
    by_period = defaultdict(set)
    for metric in metrics:
        period_key = (
            metric.metric_name,
            metric.basis,
            metric.unit,
            metric.period_bucket,
            metric.start_date,
            metric.end_date,
            metric.frame,
        )
        variant_key = metric.source_concept or "unknown_concept"
        by_period[period_key].add(variant_key)
    for variants in by_period.values():
        if len(variants) > 1:
            count += len(variants) - 1
    return count


def _period_mismatch_count(metrics: list[CanonicalMetric]) -> int:
    by_fiscal = defaultdict(set)
    for metric in metrics:
        fiscal_key = (
            metric.metric_name,
            metric.basis,
            metric.unit,
            metric.fiscal_year,
            metric.fiscal_period,
        )
        if metric.fiscal_year is not None and metric.fiscal_period is not None:
            by_fiscal[fiscal_key].add(metric.period_bucket)
    return sum(len(buckets) - 1 for buckets in by_fiscal.values() if len(buckets) > 1)


def _with_note(metric: CanonicalMetric, note: str) -> CanonicalMetric:
    notes = list(metric.reconciliation_notes) + [note]
    return (
        metric.model_copy(update={"reconciliation_notes": notes})
        if hasattr(metric, "model_copy")
        else metric.copy(update={"reconciliation_notes": notes})
    )
