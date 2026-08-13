"""Typed, period-matched FCF and capital-allocation reconciliation."""

from __future__ import annotations

from research_agent.evidence.evidence_item import EvidenceItem


def build_capital_allocation_bridge_evidence(
    *,
    ticker: str,
    as_of_date: str,
    evidence_items: list[EvidenceItem],
    period_start: str | None,
    period_end: str | None,
    currency: str,
) -> list[EvidenceItem]:
    if not period_start or not period_end:
        return []
    room16_fcf = _exact_metric(
        evidence_items,
        "free_cash_flow_current_period",
        period_start=period_start,
        period_end=period_end,
    )
    distributions = _exact_metric(
        evidence_items,
        "shareholder_distributions_current_period",
        period_start=period_start,
        period_end=period_end,
    )
    if room16_fcf is None or distributions is None:
        return []

    acquisition_components = _deduplicate_acquisition_components([
        item
        for item in evidence_items
        if item.value is not None
        and str(item.currency or currency).upper() == currency.upper()
        and any(
            "acquisition_net_cash_paid" in metric
            or "acquisition_prior_period_holdback" in metric
            for metric in item.supports_metrics
        )
        and _period_matches(item, period_start, period_end)
    ])
    issuer_fcf = _issuer_defined_fcf(
        evidence_items,
        period_start=period_start,
        period_end=period_end,
        currency=currency,
    )
    if not acquisition_components and issuer_fcf is None:
        return []

    acquisition_cash = sum(float(item.value) for item in acquisition_components)
    room16_value = float(room16_fcf.value)
    distributions_value = float(distributions.value)
    source_lineage = list(
        dict.fromkeys(
            [
                room16_fcf.source_id,
                distributions.source_id,
                *(item.source_id for item in acquisition_components),
                *([issuer_fcf.source_id] if issuer_fcf else []),
            ]
        )
    )
    common = {
        "ticker": ticker.upper(),
        "claim_type": "financial_metric",
        "source_id": room16_fcf.source_id,
        "source_type": "derived_calculation",
        "authority_rank": 1,
        "unit": currency.upper(),
        "currency": currency.upper(),
        "dimension": "currency",
        "display_unit": currency.upper(),
        "period": f"{period_start}..{period_end}",
        "period_kind": "duration",
        "presentation_basis": "period_total",
        "period_start": period_start,
        "period_end": period_end,
        "date": period_end,
        "provenance_class": "derived_calculation",
        "source_lineage": source_lineage,
        "confidence": "high",
    }
    results: list[EvidenceItem] = []
    if acquisition_components:
        results.append(
            EvidenceItem(
                evidence_id=f"{ticker.upper()}_CAPITAL_ALLOCATION_ACQUISITION_CASH_{period_end}",
                statement="Period-matched acquisition cash paid, including prior-period holdbacks paid in the current period.",
                value=acquisition_cash,
                normalized_value=acquisition_cash,
                supports_metrics=["capital_allocation_acquisition_cash_current_period"],
                formula_id="sum_period_matched_acquisition_cash_components",
                formula_operands={
                    item.supports_metrics[0]: float(item.value)
                    for item in acquisition_components
                },
                **common,
            )
        )
    room16_residual = room16_value - distributions_value - acquisition_cash
    results.append(
        EvidenceItem(
            evidence_id=f"{ticker.upper()}_CAPITAL_ALLOCATION_ROOM16_RESIDUAL_{period_end}",
            statement="Room16 normalized FCF less shareholder distributions and period-matched acquisition cash.",
            value=room16_residual,
            normalized_value=room16_residual,
            supports_metrics=["capital_allocation_room16_fcf_residual_current_period"],
            formula_id="room16_fcf_less_distributions_and_acquisition_cash",
            formula_operands={
                "room16_normalized_fcf": room16_value,
                "shareholder_distributions": distributions_value,
                "acquisition_cash": acquisition_cash,
            },
            **common,
        )
    )
    if issuer_fcf is not None:
        issuer_value = float(issuer_fcf.value)
        results.extend(
            [
                EvidenceItem(
                    evidence_id=f"{ticker.upper()}_ISSUER_DEFINED_FCF_CURRENT_PERIOD_{period_end}",
                    statement="Issuer-defined free cash flow for the same reporting period.",
                    value=issuer_value,
                    raw_value=issuer_fcf.raw_value,
                    normalized_value=issuer_value,
                    source_scale=issuer_fcf.source_scale,
                    source_sign=issuer_fcf.source_sign,
                    supports_metrics=["issuer_defined_fcf_current_period"],
                    formula_id="identity_from_period_matched_issuer_fcf",
                    formula_operands={"issuer_defined_fcf": issuer_value},
                    **common,
                ),
                EvidenceItem(
                    evidence_id=f"{ticker.upper()}_CAPITAL_ALLOCATION_ISSUER_RESIDUAL_{period_end}",
                    statement="Issuer-defined FCF less shareholder distributions and period-matched acquisition cash.",
                    value=issuer_value - distributions_value - acquisition_cash,
                    normalized_value=issuer_value - distributions_value - acquisition_cash,
                    supports_metrics=["capital_allocation_issuer_fcf_residual_current_period"],
                    formula_id="issuer_fcf_less_distributions_and_acquisition_cash",
                    formula_operands={
                        "issuer_defined_fcf": issuer_value,
                        "shareholder_distributions": distributions_value,
                        "acquisition_cash": acquisition_cash,
                    },
                    **common,
                ),
                EvidenceItem(
                    evidence_id=f"{ticker.upper()}_FCF_DEFINITION_DIFFERENCE_{period_end}",
                    statement="Period-matched difference between issuer-defined and Room16 normalized FCF.",
                    value=issuer_value - room16_value,
                    normalized_value=issuer_value - room16_value,
                    supports_metrics=["fcf_definition_difference_current_period"],
                    formula_id="issuer_defined_fcf_minus_room16_normalized_fcf",
                    formula_operands={
                        "issuer_defined_fcf": issuer_value,
                        "room16_normalized_fcf": room16_value,
                    },
                    **common,
                ),
            ]
        )
    return results


def _deduplicate_acquisition_components(items: list[EvidenceItem]) -> list[EvidenceItem]:
    """Collapse one economic cash fact emitted by more than one SEC adapter."""

    chosen: dict[tuple[str, float, str, str], EvidenceItem] = {}
    for item in items:
        metric = " ".join(item.supports_metrics).casefold()
        role = (
            "prior_period_holdback"
            if "prior_period_holdback" in metric
            else "net_cash_paid"
        )
        key = (
            role,
            float(item.value or 0.0),
            str(item.period_start or ""),
            str(item.period_end or ""),
        )
        current = chosen.get(key)
        # The filing-topic adapter carries the explicit transaction role and
        # wins deterministically over a duplicate broad operating-KPI scan.
        if current is None or (
            "filing_transactions_" in metric
            and "filing_transactions_" not in " ".join(current.supports_metrics).casefold()
        ):
            chosen[key] = item
    return sorted(chosen.values(), key=lambda item: item.evidence_id)


def _exact_metric(
    items: list[EvidenceItem],
    metric_name: str,
    *,
    period_start: str,
    period_end: str,
) -> EvidenceItem | None:
    candidates = [
        item
        for item in items
        if item.value is not None
        and metric_name in item.supports_metrics
        and _period_matches(item, period_start, period_end)
    ]
    return sorted(candidates, key=lambda item: (0 if item.formula_id else 1, item.evidence_id))[0] if candidates else None


def _issuer_defined_fcf(
    items: list[EvidenceItem],
    *,
    period_start: str,
    period_end: str,
    currency: str,
) -> EvidenceItem | None:
    candidates = [
        item
        for item in items
        if item.value is not None
        and item.provenance_class == "primary_source"
        and str(item.currency or currency).upper() == currency.upper()
        and any(
            "free_cash_flow" in metric
            and "guidance" not in metric
            and "ex_sustainability_growth" not in metric
            for metric in item.supports_metrics
        )
        and _period_matches(item, period_start, period_end)
    ]
    return sorted(candidates, key=lambda item: (item.authority_rank, item.evidence_id))[0] if candidates else None


def _period_matches(item: EvidenceItem, period_start: str, period_end: str) -> bool:
    if item.period_start and item.period_end:
        return item.period_start == period_start and item.period_end == period_end
    return str(item.period or "") == f"{period_start}..{period_end}"
