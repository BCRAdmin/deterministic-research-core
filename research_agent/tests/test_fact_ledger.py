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
    assert facts["sbc_to_revenue"]["unit"] == "fraction (1.0 = 100%)"
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


def test_fact_ledger_preserves_duration_periods_and_ratio_units():
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
            unit="shares",
            period="FY2026_Q2",
            date="2026-06-30",
            period_start="2026-01-01",
            period_end="2026-06-30",
            duration_days=180,
            supports_metrics=["diluted_share_count_yoy"],
            raw_value=0.02,
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
    assert fact["period_kind"] == "duration"
    assert fact["period_type"] == "ytd"
    assert fact["presentation_basis"] == "year_to_date"
    assert fact["period_start"] == "2026-01-01"


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
