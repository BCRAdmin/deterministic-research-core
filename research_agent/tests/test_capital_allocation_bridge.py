from research_agent.evidence.capital_allocation_bridge import (
    build_capital_allocation_bridge_evidence,
)
from research_agent.evidence.evidence_item import EvidenceItem


def _item(evidence_id, metric, value, *, source_id="WM_SEC", provenance="primary_source"):
    return EvidenceItem(
        evidence_id=evidence_id,
        ticker="WM",
        claim_type="financial_metric",
        source_id=source_id,
        source_type="sec_filing",
        authority_rank=1,
        statement=metric,
        value=value,
        raw_value=value,
        normalized_value=value,
        unit="USD",
        currency="USD",
        period="2026-01-01..2026-06-30",
        period_kind="duration",
        presentation_basis="period_total",
        period_start="2026-01-01",
        period_end="2026-06-30",
        date="2026-06-30",
        supports_metrics=[metric],
        provenance_class=provenance,
    )


def test_capital_allocation_bridge_reconciles_both_fcf_definitions_and_acquisition_cash():
    items = [
        _item(
            "ROOM16_FCF",
            "free_cash_flow_current_period",
            1_947_000_000,
            source_id="ROOM16_DERIVED",
            provenance="derived_calculation",
        ),
        _item(
            "DISTRIBUTIONS",
            "shareholder_distributions_current_period",
            1_767_000_000,
            source_id="ROOM16_DERIVED",
            provenance="derived_calculation",
        ),
        _item("ACQUISITION_CASH", "filing_transactions_acquisition_net_cash_paid_usd", 85_000_000),
        _item("PRIOR_HOLDBACK", "filing_transactions_acquisition_prior_period_holdback_usd", 13_000_000),
        _item(
            "ISSUER_ADJUSTED_FCF",
            "operating_kpi_free_cash_flow_ex_sustainability_growth_actual_6m_2026",
            2_160_000_000,
        ),
        _item("ISSUER_FCF", "operating_kpi_free_cash_flow_6m_2026", 2_024_000_000),
    ]

    bridge = build_capital_allocation_bridge_evidence(
        ticker="WM",
        as_of_date="2026-08-11",
        evidence_items=items,
        period_start="2026-01-01",
        period_end="2026-06-30",
        currency="USD",
    )
    values = {
        item.supports_metrics[0]: item.value
        for item in bridge
    }
    assert values == {
        "capital_allocation_acquisition_cash_current_period": 98_000_000,
        "capital_allocation_room16_fcf_residual_current_period": 82_000_000,
        "issuer_defined_fcf_current_period": 2_024_000_000,
        "capital_allocation_issuer_fcf_residual_current_period": 159_000_000,
        "fcf_definition_difference_current_period": 77_000_000,
    }
    assert all(item.period_start == "2026-01-01" for item in bridge)
    assert all(item.period_end == "2026-06-30" for item in bridge)


def test_capital_allocation_bridge_deduplicates_same_acquisition_cash_across_adapters():
    items = [
        _item(
            "ROOM16_FCF",
            "free_cash_flow_current_period",
            1_947_000_000,
            source_id="ROOM16_DERIVED",
            provenance="derived_calculation",
        ),
        _item(
            "DISTRIBUTIONS",
            "shareholder_distributions_current_period",
            1_767_000_000,
            source_id="ROOM16_DERIVED",
            provenance="derived_calculation",
        ),
        _item("SEC_TOPIC_CASH", "filing_transactions_acquisition_net_cash_paid_usd", 85_000_000),
        _item("SEC_KPI_CASH", "operating_kpi_acquisition_net_cash_paid_6m_2026_amount", 85_000_000),
        _item("PRIOR_HOLDBACK", "filing_transactions_acquisition_prior_period_holdback_usd", 13_000_000),
    ]

    bridge = build_capital_allocation_bridge_evidence(
        ticker="WM",
        as_of_date="2026-08-11",
        evidence_items=items,
        period_start="2026-01-01",
        period_end="2026-06-30",
        currency="USD",
    )
    acquisition = next(
        item for item in bridge
        if item.supports_metrics == ["capital_allocation_acquisition_cash_current_period"]
    )

    assert acquisition.value == 98_000_000
    assert len(acquisition.formula_operands) == 2
