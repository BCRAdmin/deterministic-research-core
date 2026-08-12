from __future__ import annotations

import pytest

from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.evidence.fact_ledger import FactLedgerError, build_fact_ledger
from research_agent.research_core.ingestion.source_registry import (
    SourceRegistry,
    SourceRegistryEntry,
)
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import DataPacket, PriceBasis


def _fact_inputs():
    ticker = "GENERIC"
    as_of = "2026-07-01"
    sec_source = "SEC_GENERIC_DERIVED_TTM"
    price_source = "GENERIC_EXCHANGE"
    data_packet = DataPacket(
        ticker=ticker,
        company_name="Generic Company",
        as_of_date=as_of,
        price_basis=PriceBasis(
            close=100.0,
            date=as_of,
            currency="USD",
            source=price_source,
        ),
        source_registry_id=f"{ticker}_{as_of}",
    )
    claims = [
        ResearchClaim(
            claim_id="GENERIC_CLAIM_001",
            agent="deterministic_content_generator",
            claim="Exact structured facts.",
            evidence_metrics=[],
            metric_refs=[],
            metric_values={
                "close": 100.0,
                "revenue_ttm": 1_000.0,
                "free_cash_flow_ttm": 100.0,
                "shareholder_distributions_ttm": 125.0,
                "shareholder_distributions_minus_fcf_ttm": 25.0,
                "ev_to_sales": 2.0,
                "sbc_to_revenue": 0.05,
            },
            source_ids=[sec_source, price_source],
            confidence="high",
        )
    ]
    evidence = EvidenceLedger(
        ticker=ticker,
        as_of_date=as_of,
        evidence_items=[
            EvidenceItem(
                evidence_id=f"GENERIC_{metric.upper()}",
                ticker=ticker,
                claim_type=claim_type,
                source_id=source_id,
                source_type=source_type,
                authority_rank=authority_rank,
                statement=f"{metric} exact evidence.",
                value=value,
                unit=unit,
                period=period,
                date=as_of,
                supports_metrics=[metric],
                formula_id=formula_id,
                formula_operands=formula_operands,
                source_lineage=source_lineage,
            )
            for (
                metric,
                value,
                unit,
                period,
                claim_type,
                source_id,
                source_type,
                authority_rank,
                formula_id,
                formula_operands,
                source_lineage,
            ) in [
                (
                    "close",
                    100.0,
                    "USD",
                    "daily_history",
                    "price_data",
                    price_source,
                    "exchange_ohlcv",
                    2,
                    None,
                    {},
                    [],
                ),
                (
                    "revenue_ttm",
                    1_000.0,
                    "USD",
                    "TTM",
                    "financial_metric",
                    sec_source,
                    "sec_filing",
                    1,
                    "sum_four_contiguous_quarters",
                    {"q1": 250.0, "q2": 250.0, "q3": 250.0, "q4": 250.0},
                    [],
                ),
                (
                    "free_cash_flow_ttm",
                    100.0,
                    "USD",
                    "TTM",
                    "financial_metric",
                    sec_source,
                    "sec_filing",
                    1,
                    "cfo_minus_capex",
                    {"operating_cash_flow_ttm": 120.0, "capex_ttm": 20.0},
                    [],
                ),
                (
                    "shareholder_distributions_ttm",
                    125.0,
                    "USD",
                    "TTM",
                    "financial_metric",
                    sec_source,
                    "sec_filing",
                    1,
                    "buybacks_ttm_plus_dividends_paid_ttm",
                    {"buybacks": 50.0, "dividends_paid": 75.0},
                    [],
                ),
                (
                    "shareholder_distributions_minus_fcf_ttm",
                    25.0,
                    "USD",
                    "TTM",
                    "financial_metric",
                    sec_source,
                    "sec_filing",
                    1,
                    "shareholder_distributions_ttm_minus_free_cash_flow_ttm",
                    {
                        "shareholder_distributions_ttm": 125.0,
                        "free_cash_flow_ttm": 100.0,
                    },
                    [],
                ),
                (
                    "ev_to_sales",
                    2.0,
                    "multiple",
                    f"as of {as_of}",
                    "valuation_metric",
                    sec_source,
                    "sec_filing",
                    1,
                    "enterprise_value_divided_by_revenue_ttm",
                    {"enterprise_value": 2_000.0, "revenue_ttm": 1_000.0},
                    [sec_source, price_source],
                ),
                (
                    "sbc_to_revenue",
                    0.05,
                    "percent",
                    "TTM",
                    "financial_metric",
                    sec_source,
                    "sec_filing",
                    1,
                    None,
                    {},
                    [],
                ),
            ]
        ],
    )
    registry = SourceRegistry(
        registry_id=f"{ticker}_{as_of}",
        sources=[
            SourceRegistryEntry(
                source_id=sec_source,
                ticker=ticker,
                source_type="sec_filing",
                authority_rank=1,
                owner="SEC",
            ),
            SourceRegistryEntry(
                source_id=price_source,
                ticker=ticker,
                source_type="exchange_ohlcv",
                authority_rank=2,
                owner="Exchange",
            ),
        ],
    )
    return data_packet, claims, evidence, registry


def test_fact_ledger_binds_exact_values_formulas_and_sources():
    data_packet, claims, evidence, registry = _fact_inputs()

    payload = build_fact_ledger(
        data_packet=data_packet,
        claims=claims,
        evidence_ledger=evidence,
        source_registry=registry,
    )

    facts = {fact["metric"]: fact for fact in payload["claims"]}
    assert facts["ev_to_sales"]["formula_operands"] == {
        "enterprise_value": 2_000.0,
        "revenue_ttm": 1_000.0,
    }
    assert facts["ev_to_sales"]["source_ids"] == [
        "SEC_GENERIC_DERIVED_TTM",
        "GENERIC_EXCHANGE",
    ]
    assert facts["sbc_to_revenue"]["unit"] == "percent"
    assert facts["sbc_to_revenue"]["dimension"] == "percent"
    assert facts[
        "shareholder_distributions_minus_fcf_ttm"
    ]["formula_operands"] == {
        "free_cash_flow_ttm": 100.0,
        "shareholder_distributions_ttm": 125.0,
    }
    assert {source["source_type"] for source in payload["sources"]} == {
        "SEC",
        "PRICE_VENDOR",
    }


def test_fact_ledger_preserves_unclaimed_not_applicable_table_cells() -> None:
    data_packet, claims, evidence, registry = _fact_inputs()
    metric = "operating_kpi_integration_costs_current_collection"
    evidence.evidence_items.append(
        EvidenceItem(
            evidence_id="GENERIC_INTEGRATION_DASH",
            ticker="GENERIC",
            claim_type="financial_metric",
            source_id="SEC_GENERIC_DERIVED_TTM",
            source_type="sec_filing",
            authority_rank=1,
            statement="Integration costs table reports a dash for collection.",
            value=0.0,
            raw_value=0.0,
            unit="currency",
            currency="USD",
            dimension="currency",
            display_unit="USD",
            source_scale="million",
            source_sign=1,
            row_metric="integration_costs",
            column_metric="collection",
            segment="collection",
            source_cell_status="not_applicable_dash",
            period_kind="duration",
            presentation_basis="period_total",
            period_start="2026-04-01",
            period_end="2026-06-30",
            date="2026-07-01",
            supports_metrics=[metric],
        )
    )

    payload = build_fact_ledger(
        data_packet=data_packet,
        claims=claims,
        evidence_ledger=evidence,
        source_registry=registry,
    )

    fact = next(item for item in payload["claims"] if item["metric"] == metric)
    assert fact["value"] == 0.0
    assert fact["source_cell_status"] == "not_applicable_dash"
    assert fact["column_metric"] == "collection"
    assert fact["research_claim_ids"] == []
    assert fact["claim_bound_evidence_ids"] == []


def test_fact_ledger_preserves_comparison_periods_and_ratio_units():
    data_packet, claims, evidence, registry = _fact_inputs()
    claims[0].metric_values["diluted_share_count_yoy"] = 0.02
    evidence.evidence_items.append(
        EvidenceItem(
            evidence_id="GENERIC_SHARE_CHANGE",
            ticker="GENERIC",
            claim_type="financial_metric",
            source_id="SEC_GENERIC_DERIVED_TTM",
            source_type="sec_filing",
            authority_rank=1,
            statement="Diluted shares increased two percent.",
            value=0.02,
            unit="ratio",
            period="CY2025Q2..CY2026Q2",
            date="2026-06-30",
            supports_metrics=["diluted_share_count_yoy"],
            raw_value=0.02,
            formula_id="matching_quarter_diluted_share_count_yoy_change",
            formula_operands={
                "current_diluted_share_count": 102.0,
                "prior_diluted_share_count": 100.0,
            },
        )
    )

    payload = build_fact_ledger(
        data_packet=data_packet,
        claims=claims,
        evidence_ledger=evidence,
        source_registry=registry,
    )

    fact = next(
        item for item in payload["claims"]
        if item["metric"] == "diluted_share_count_yoy"
    )
    assert fact["unit"] == "ratio"
    assert fact["period_start"] == fact["current_period_start"] == "2026-04-01"
    assert fact["period_end"] == fact["current_period_end"] == "2026-06-30"
    assert fact["period_kind"] == "comparison"
    assert fact["period_type"] == "calculated"
    assert fact["presentation_basis"] == "period_over_period_comparison"
    assert fact["comparison_period_start"] == "2025-04-01"
    assert fact["comparison_period_end"] == "2025-06-30"


def test_fact_ledger_never_labels_a_duration_fact_as_spot() -> None:
    data_packet, claims, evidence, registry = _fact_inputs()
    claims[0].metric_values["operating_kpi_volume"] = 42.0
    evidence.evidence_items.append(
        EvidenceItem(
            evidence_id="GENERIC_DURATION_KPI",
            ticker="GENERIC",
            claim_type="financial_metric",
            source_id="SEC_GENERIC_DERIVED_TTM",
            source_type="sec_filing",
            authority_rank=1,
            statement="Volume for the six months ended June 30.",
            value=42.0,
            unit="count",
            period="6M ended 2026-06-30",
            period_start="2026-01-01",
            period_end="2026-06-30",
            date="2026-06-30",
            supports_metrics=["operating_kpi_volume"],
            raw_value=42.0,
        )
    )

    payload = build_fact_ledger(
        data_packet=data_packet,
        claims=claims,
        evidence_ledger=evidence,
        source_registry=registry,
    )

    fact = next(
        item for item in payload["claims"]
        if item["metric"] == "operating_kpi_volume"
    )
    assert fact["period_kind"] == "duration"
    assert fact["period_type"] == "duration"
    assert fact["presentation_basis"] == "period_total"


def test_fact_ledger_uses_period_end_as_asof_for_instant_fact() -> None:
    data_packet, claims, evidence, registry = _fact_inputs()
    metric = "share_repurchase_authorization_remaining"
    claims[0].metric_values[metric] = 2_000_000_000.0
    evidence.evidence_items.append(
        EvidenceItem(
            evidence_id="GENERIC_REPURCHASE_AUTHORIZATION",
            ticker="GENERIC",
            claim_type="financial_metric",
            source_id="SEC_GENERIC_DERIVED_TTM",
            source_type="sec_filing",
            authority_rank=1,
            statement="Remaining authorization as of June 30, 2026.",
            value=2_000_000_000.0,
            unit="USD",
            currency="USD",
            period="as of 2026-06-30",
            period_kind="instant",
            presentation_basis="point_in_time",
            period_end="2026-06-30",
            date="2026-07-29",
            supports_metrics=[metric],
            raw_value=2.0,
            source_scale="billion",
        )
    )

    payload = build_fact_ledger(
        data_packet=data_packet,
        claims=claims,
        evidence_ledger=evidence,
        source_registry=registry,
    )

    fact = next(item for item in payload["claims"] if item["metric"] == metric)
    assert fact["period_kind"] == "instant"
    assert fact["period_end"] == fact["asof"] == "2026-06-30"


def test_fact_ledger_resolves_compact_sec_lineage_to_registered_source_id():
    data_packet, claims, evidence, registry = _fact_inputs()
    revenue = next(
        item for item in evidence.evidence_items
        if "revenue_ttm" in item.supports_metrics
    )
    revenue.source_lineage = ["SEC_0001628280-26-050503"]
    canonical_sec_source = "SEC_0000021344_0001628280-26-050503"
    registry.sources.append(
        SourceRegistryEntry(
            source_id=canonical_sec_source,
            ticker="GENERIC",
            source_type="sec_filing",
            authority_rank=1,
            owner="SEC",
        )
    )

    payload = build_fact_ledger(
        data_packet=data_packet,
        claims=claims,
        evidence_ledger=evidence,
        source_registry=registry,
    )
    revenue_fact = next(
        fact for fact in payload["claims"] if fact["metric"] == "revenue_ttm"
    )

    assert revenue_fact["source_ids"] == [
        "SEC_GENERIC_DERIVED_TTM",
        canonical_sec_source,
    ]


def test_fact_ledger_fails_when_claim_value_has_no_exact_evidence():
    data_packet, claims, evidence, registry = _fact_inputs()
    claims[0].metric_values["close"] = 101.0
    evidence.evidence_items.append(
        EvidenceItem(
            evidence_id="GENERIC_PSEUDO_CLOSE",
            ticker="GENERIC",
            claim_type="price_data",
            source_id="GENERIC_EXCHANGE",
            source_type="exchange_ohlcv",
            authority_rank=2,
            statement="GENERIC_EXCHANGE supports close.",
            value=101.0,
            supports_metrics=["close"],
        )
    )

    with pytest.raises(FactLedgerError, match="no exact evidence value for close=101.0"):
        build_fact_ledger(
            data_packet=data_packet,
            claims=claims,
            evidence_ledger=evidence,
            source_registry=registry,
        )
