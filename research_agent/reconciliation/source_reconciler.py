from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Iterable, Optional

from research_agent.reconciliation.canonical_financials import CanonicalFinancials, CanonicalMetric
from research_agent.reconciliation.confidence_scoring import score_confidence
from research_agent.reconciliation.fact_deduplicator import deduplicate_facts
from research_agent.reconciliation.gaap_nongaap_classifier import classify_metric_basis
from research_agent.reconciliation.period_resolver import resolve_period, validate_resolved_period
from research_agent.reconciliation.restatement_resolver import prefer_restatement
from research_agent.reconciliation.unit_normalizer import normalize_value, validate_unit_for_metric
from research_agent.sources.sec.companyfacts_parser import ParsedFact


MAX_CURRENT_FINANCIAL_AGE_DAYS = 550


def reconcile_metric(metric_name: str, candidate_metrics: Iterable[CanonicalMetric]):
    candidates = list(candidate_metrics)
    if not candidates:
        return [], []

    warnings: list[dict] = []
    ignored_variant_count = _ignored_variant_count(candidates)
    if ignored_variant_count:
        warnings.append({
            "severity": "info",
            "code": "SOURCE_FRAME_VARIANT_IGNORED",
            "metric": metric_name,
            "count": ignored_variant_count,
            "message": f"Ignored {ignored_variant_count} SEC frame/concept variants across distinct periods for {metric_name}.",
        })

    period_mismatch_count = _period_mismatch_count(candidates)
    if period_mismatch_count:
        warnings.append({
            "severity": "info",
            "code": "PERIOD_TYPE_MISMATCH_IGNORED",
            "metric": metric_name,
            "count": period_mismatch_count,
            "message": f"Ignored {period_mismatch_count} annual/quarterly/YTD period-type variants for {metric_name}.",
        })

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
                warnings.append({
                    "severity": "info",
                    "code": "PERIOD_TYPE_MISMATCH_IGNORED",
                    "metric": metric_name,
                    "period_type": top.period_bucket,
                    "count": 1,
                    "message": (
                        f"Ignored YTD source disagreement for {metric_name} ({top.period}); "
                        "YTD facts are kept separate and are not used as quarterly/annual canonical metrics."
                    ),
                })
                top = _with_note(top, "Ignored YTD source disagreement because YTD facts are not merged into quarterly/annual metrics.")
            else:
                warnings.append({
                    "severity": "warning",
                    "code": "TRUE_SOURCE_VALUE_DISAGREEMENT",
                    "metric": metric_name,
                    "basis": top.basis,
                    "period_type": top.period_bucket,
                    "message": f"Comparable sources disagree for {metric_name} ({top.basis}, {top.period_bucket}, {top.period}).",
                })
                top = _with_note(top, "Selected highest-confidence source among disagreeing values.")
        canonical.append(top)

    warnings.extend(_guidance_consensus_warnings(metric_name, canonical))
    warnings.extend(_low_confidence_warnings(canonical))
    return canonical, warnings


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
        evidence_ids=[evidence_id] if evidence_id else [],
        confidence=confidence,
        reconciliation_notes=[
            f"Resolved as {resolved.period_type}/{resolved.period_bucket} period {resolved.period_label}.",
        ],
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

    return CanonicalFinancials(ticker=ticker.upper(), as_of_date=as_of_date, metrics=canonical_metrics), warnings


def canonical_financials_to_fundamentals(canonical: CanonicalFinancials) -> dict:
    fundamentals = {
        "quarterly": {},
        "annual": {},
        "balance_sheet": {},
        "share_data": {},
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
    }
    for metric_name in duration_metrics:
        values, issue = _compatible_trailing_period_values(canonical, metric_name)
        if len(values) == 4:
            fundamentals["quarterly"][metric_name] = values
        else:
            annual = _latest_annual_metric(canonical, metric_name)
            if annual is not None:
                fundamentals["annual"][metric_name] = annual.value
            if issue:
                fundamentals["reconciliation_issues"].append(issue)

    balance_sheet_metrics = {
        "cash_and_equivalents",
        "short_term_investments",
        "current_assets",
        "current_liabilities",
        "equity",
        "total_debt",
    }
    for metric_name in balance_sheet_metrics:
        selected = _latest_current_metric(canonical, metric_name, require_gaap=True)
        if selected is not None:
            fundamentals["balance_sheet"][metric_name] = selected.value
        elif canonical.metrics_for(metric_name):
            fundamentals["reconciliation_issues"].append(
                _stale_metric_issue(metric_name)
            )

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
        elif canonical.metrics_for(metric_name):
            fundamentals["reconciliation_issues"].append(
                _stale_metric_issue(metric_name)
            )
    return fundamentals


def _compatible_trailing_period_values(canonical: CanonicalFinancials, metric_name: str) -> tuple[list[float], Optional[dict]]:
    quarterly = _dedupe_period_metrics([
        metric for metric in canonical.metrics_for(metric_name)
        if metric.period_bucket == "quarterly"
        and metric.basis == "gaap"
        and _is_current_metric(canonical, metric)
        and metric.start_date
        and metric.end_date
        and metric.duration_days is not None
        and 70 <= metric.duration_days <= 110
    ])
    if len(quarterly) >= 4:
        return [metric.value for metric in quarterly[-4:]], None

    annual = _latest_annual_metric(canonical, metric_name)
    if annual is not None:
        derived = _derive_q4_and_trailing_values(annual, quarterly)
        if derived is not None:
            return derived, None

    available = canonical.metrics_for(metric_name)
    if available and not any(_is_current_metric(canonical, metric) for metric in available):
        return [], _stale_metric_issue(metric_name)
    return [], {
        "severity": "warning",
        "code": "MISSING_COMPATIBLE_DENOMINATOR" if metric_name == "revenue" else "MISSING_COMPATIBLE_NUMERATOR",
        "metric": metric_name,
        "message": f"Could not build four compatible quarterly periods for {metric_name}; ratio inputs should use annual fallback or remain unavailable.",
    }


def _dedupe_period_metrics(metrics: list[CanonicalMetric]) -> list[CanonicalMetric]:
    by_dates: dict[tuple[str, str], CanonicalMetric] = {}
    for metric in sorted(
        metrics,
        key=lambda item: (
            item.end_date or "",
            _confidence_rank(item.confidence),
            1 if item.frame else 0,
        ),
    ):
        if not metric.start_date or not metric.end_date:
            continue
        key = (metric.start_date, metric.end_date)
        existing = by_dates.get(key)
        if existing is None or _confidence_rank(metric.confidence) >= _confidence_rank(existing.confidence):
            by_dates[key] = metric
    return sorted(by_dates.values(), key=lambda item: item.end_date or "")


def _latest_annual_metric(canonical: CanonicalFinancials, metric_name: str) -> Optional[CanonicalMetric]:
    annual = [
        metric for metric in canonical.metrics_for(metric_name)
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
        if (not require_gaap or metric.basis == "gaap")
        and _is_current_metric(canonical, metric)
    ]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda metric: (
            metric.end_date or "",
            _confidence_rank(metric.confidence),
            1 if metric.frame else 0,
        ),
        reverse=True,
    )[0]


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


def _derive_q4_and_trailing_values(annual: CanonicalMetric, quarterly: list[CanonicalMetric]) -> Optional[list[float]]:
    annual_quarters = [
        metric for metric in quarterly
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
        metric for metric in quarterly
        if metric.start_date and metric.start_date > annual_end
    ]
    values = [metric.value for metric in first_three[-3:]] + [q4_value]
    if trailing_after_annual:
        combined = values + [metric.value for metric in trailing_after_annual]
        return combined[-4:]
    return values[-4:]


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
                warnings.append({
                    "severity": "warning",
                    "code": "CONSENSUS_GUIDANCE_MISMATCH",
                    "metric": metric_name,
                    "message": f"Consensus and company guidance differ by {diff:.1%}.",
                })
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
    if metric_name in {"operating_cash_flow", "capex", "sbc"}:
        return "cash_flow"
    if metric_name in {"cash_and_equivalents", "short_term_investments", "total_assets", "total_liabilities", "stockholders_equity"}:
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
    return metric.model_copy(update={"reconciliation_notes": notes}) if hasattr(metric, "model_copy") else metric.copy(update={"reconciliation_notes": notes})
