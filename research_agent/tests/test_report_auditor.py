import json
import subprocess
import sys
from pathlib import Path

import pytest

from research_agent.audit.markdown_numeric_extractor import extract_numeric_claims
from research_agent.audit.report_linter import (
    _numbers_close_for_evidence,
    audit_markdown_report,
)
from research_agent.decision.rating_engine import build_decision_packet
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.reconciliation.canonical_financials import CanonicalFinancials, CanonicalMetric
from research_agent.research_core.ingestion.source_registry import SourceRegistry, SourceRegistryEntry
from research_agent.research_core.models.claims import ResearchClaim
from research_agent.research_core.models.data_packet import (
    DataPacket,
    EventInfo,
    FiscalContext,
    PriceBasis,
)
from research_agent.research_core.models.metrics_packet import (
    FundamentalMetrics,
    IssuerRiskAssessment,
    MetricsPacket,
    TechnicalMetrics,
    ValuationMetrics,
    ValuationScenario,
    ValuationSensitivity,
)
from research_agent.research_core.models.validation_report import ValidationReport
from research_agent.research_core.reporting.report_builder import render_markdown_report


FIXTURES = Path(__file__).parent / "fixtures"


def test_structured_numeric_matching_respects_display_rounding_and_semantic_sign():
    assert _numbers_close_for_evidence(
        0.7,
        0.006818093271515955,
        reported_unit="percent",
        evidence_unit="percent",
    )
    assert _numbers_close_for_evidence(
        0.5,
        -0.004699480583724957,
        reported_unit="percent",
        evidence_unit="percent",
        nearby_text="The share count decreased by 0.5%.",
    )
    assert _numbers_close_for_evidence(
        22_000_000,
        -22_000_000,
        reported_unit="usd",
        evidence_unit="USD",
        nearby_text="Revenue from volume decreased $22 million.",
    )
    assert not _numbers_close_for_evidence(
        22_000_000,
        -22_000_000,
        reported_unit="usd",
        evidence_unit="USD",
        nearby_text="Revenue increased $22 million.",
    )
    assert _numbers_close_for_evidence(
        69_154,
        69_154_000_000,
        reported_unit="usd",
        evidence_unit="currency",
        evidence_raw_value=69_154,
        evidence_source_scale="million",
    )
    assert not _numbers_close_for_evidence(
        69_155,
        69_154_000_000,
        reported_unit="usd",
        evidence_unit="currency",
        evidence_raw_value=69_154,
        evidence_source_scale="base",
    )


def load_fixture(name, filename):
    path = FIXTURES / name / filename
    if filename.endswith(".json"):
        return json.loads(path.read_text(encoding="utf-8"))
    return path.read_text(encoding="utf-8")


def audit_fixture(name):
    return audit_markdown_report(
        markdown=load_fixture(name, "bad_report.md"),
        metrics_packet=MetricsPacket(**load_fixture(name, "metrics_packet.json")),
        validation_report=ValidationReport(**load_fixture(name, "validation_report.json")),
        source_registry=SourceRegistry(**load_fixture(name, "source_registry.json")),
    )


def valuation_source_registry(ticker="RKLB"):
    return SourceRegistry(
        registry_id=f"{ticker}_sources",
        sources=[
            SourceRegistryEntry(
                source_id=f"{ticker}_SEC",
                ticker=ticker,
                source_type="sec_filing",
                authority_rank=1,
                used_for=["revenue", "shares", "debt", "cash"],
            ),
            SourceRegistryEntry(
                source_id=f"{ticker}_IR",
                ticker=ticker,
                source_type="company_ir",
                authority_rank=1,
                used_for=["revenue", "cash", "debt"],
            ),
            SourceRegistryEntry(
                source_id=f"{ticker}_PRICE",
                ticker=ticker,
                source_type="exchange_ohlcv",
                authority_rank=2,
                used_for=["price", "price_data", "close"],
            ),
        ],
    )


def simple_metrics(
    *,
    ticker="RKLB",
    revenue_ttm=622_495_000,
    market_cap=75_540_078_249.93611,
    enterprise_value=73_938_534_249.93611,
    ev_to_sales=118.77771588516552,
):
    return MetricsPacket(
        ticker=ticker,
        as_of_date="2026-05-15",
        technical=TechnicalMetrics(indicator_date="2026-05-15", close=124.77),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=revenue_ttm,
            operating_income_ttm=-250_000_000,
            free_cash_flow_ttm=-220_123_000,
            cash_and_investments=1_654_697_000,
            total_debt=53_153_000,
            diluted_share_count=605_434_642,
        ),
        valuation=ValuationMetrics(
            market_cap=market_cap,
            enterprise_value=enterprise_value,
            ev_to_sales=ev_to_sales,
        ),
    )


def test_markdown_numeric_extractor_normalizes_german_cash_claim():
    claims = extract_numeric_claims("Der Free Cashflow TTM beträgt 58,1 Mrd. $.")
    claim = next(item for item in claims if item.unit == "usd")

    assert claim.normalized_value == 58100000000
    assert claim.possible_metric == "free_cash_flow_ttm"
    assert claim.period_hint == "ttm"

    huf_claim = extract_numeric_claims("Revenue TTM is 65.51B HUF.")[0]
    assert huf_claim.normalized_value == pytest.approx(65_510_000_000)
    assert huf_claim.unit == "huf"


def test_markdown_numeric_extractor_includes_material_plain_counts() -> None:
    claims = extract_numeric_claims(
        "Paid members reached 81.0 million in fiscal 2025. "
        "<!-- room16-lineage claim=CLAIM-001 -->"
    )

    counts = [claim for claim in claims if claim.unit == "count"]
    assert [(claim.raw_text, claim.normalized_value) for claim in counts] == [
        ("81.0 million", 81_000_000.0)
    ]


def test_currency_range_lower_bound_inherits_explicit_upper_bound_scale():
    claims = extract_numeric_claims(
        "Guidance calls for adjusted EBITDA between $8.15 and $8.25 billion, "
        "FCF between $3.75 and $3.85 billion, and revenue between $26.275 and "
        "$26.475 billion."
    )

    assert [claim.normalized_value for claim in claims] == [
        8_150_000_000,
        8_250_000_000,
        3_750_000_000,
        3_850_000_000,
        26_275_000_000,
        26_475_000_000,
    ]


def test_period_matched_capital_allocation_maps_without_ttm_conflation():
    metrics = simple_metrics(ticker="WM")
    metrics.fundamentals.shareholder_distributions_current_period = 1_767_000_000
    metrics.fundamentals.free_cash_flow_current_period = 1_947_000_000
    metrics.fundamentals.shareholder_distributions_minus_fcf_current_period = -180_000_000
    markdown = (
        "From 2026-01-01 through 2026-06-30, shareholder distributions were "
        "$1.77B versus same-period FCF of $1.95B; distributions were covered "
        "by same-period FCF with $180.0M remaining. This is a period-matched "
        "capital-allocation comparison, not a TTM claim."
    )
    claims = [claim for claim in extract_numeric_claims(markdown) if claim.unit == "usd"]

    assert [claim.possible_metric for claim in claims] == [
        "shareholder_distributions_current_period",
        "free_cash_flow_current_period",
        "shareholder_distributions_minus_fcf_current_period",
    ]
    audit = audit_markdown_report(markdown=markdown, metrics_packet=metrics)
    assert not audit.has_issue("NUMERIC_MISMATCH")
    assert not audit.has_issue("UNVERIFIED_HARD_METRIC")


def test_primary_event_statement_supports_unstructured_numeric_details():
    statement = (
        "The issuer disclosed a $1 million transition bonus, an $850,000 base "
        "salary and a 105% target incentive in the filed leadership change."
    )
    ledger = EvidenceLedger(
        ticker="WM",
        as_of_date="2026-08-10",
        evidence_items=[
            EvidenceItem(
                evidence_id="WM_SEC_LEADERSHIP_EVENT",
                ticker="WM",
                claim_type="event",
                source_id="WM_SEC_LEADERSHIP",
                source_type="sec_filing",
                authority_rank=1,
                statement=statement,
                date="2026-05-13",
                confidence="high",
            )
        ],
    )

    supported = audit_markdown_report(
        markdown=statement,
        metrics_packet=simple_metrics(ticker="WM"),
        evidence_ledger=ledger,
    )
    altered = audit_markdown_report(
        markdown=statement.replace("$850,000", "$950,000"),
        metrics_packet=simple_metrics(ticker="WM"),
        evidence_ledger=ledger,
    )

    assert not supported.has_issue("UNVERIFIED_HARD_METRIC")
    assert not supported.has_issue("NUMERIC_MISMATCH")
    assert not supported.has_issue("MISSING_EVIDENCE_FOR_HARD_CLAIM")
    assert altered.has_issue("NUMERIC_MISMATCH")


def test_structured_lineage_uses_render_order_for_equal_and_near_values():
    claim = ResearchClaim(
        claim_id="WM_CLAIM_TEST",
        agent="deterministic_content_generator",
        claim=(
            "3M ended 2026-06-30: $123.0M; 6M ended 2026-06-30: $123.0M; "
            "close $226.85; 50-SMA $226.81."
        ),
        evidence_metrics=["metric_3m", "metric_6m", "close", "sma_50"],
        metric_values={
            "metric_3m": 123_000_000,
            "metric_6m": 123_000_000,
            "close": 226.85,
            "sma_50": 226.8112,
        },
        evidence_ids=["E1", "E2", "E3", "E4"],
        source_ids=["SOURCE-1"],
        numeric_mentions=["$123.0M", "$123.0M", "$226.85", "$226.81"],
        numeric_bindings=[
            {"span_id": f"WM_CLAIM_TEST:number-{index}", "metric_id": metric, "fact_id": f"F{index}", "evidence_id": f"E{index}", "source_id": "SOURCE-1", "source_locator": f"cell:{index}", "report_text": text}
            for index, (metric, text) in enumerate(
                [("metric_3m", "$123.0M"), ("metric_6m", "$123.0M"), ("close", "$226.85"), ("sma_50", "$226.81")],
                start=1,
            )
        ],
        confidence="high",
    )
    values = [123_000_000, 123_000_000, 226.85, 226.8112]
    units = ["USD", "USD", "USD", "USD"]
    ledger = EvidenceLedger(
        ticker="WM",
        as_of_date="2026-08-11",
        evidence_items=[
            EvidenceItem(
                evidence_id=f"E{index}",
                ticker="WM",
                claim_type="financial_metric",
                source_id="SOURCE-1",
                source_type="sec_filing",
                authority_rank=1,
                statement="Bound number.",
                value=value,
                unit=unit,
                supports_metrics=[metric],
            )
            for index, (value, unit, metric) in enumerate(
                zip(values, units, ["metric_3m", "metric_6m", "close", "sma_50"]),
                start=1,
            )
        ],
    )
    markdown = (
        claim.claim
        + " <!-- room16-lineage claim=WM_CLAIM_TEST evidence=E1,E2,E3,E4 -->"
    )

    audit = audit_markdown_report(
        markdown=markdown,
        metrics_packet=simple_metrics(ticker="WM"),
        evidence_ledger=ledger,
        research_claims=[claim],
    )

    assert not audit.has_issue("MISSING_EVIDENCE_FOR_HARD_CLAIM")
    assert [item.evidence_id for item in audit.numeric_claims if item.unit != "date"] == [
        "E1",
        "E2",
        "E3",
        "E4",
    ]


def test_plain_thousand_scale_is_normalized_for_structured_lineage() -> None:
    claims = extract_numeric_claims("Volume was 300.0 thousand customers.")

    assert len(claims) == 1
    assert claims[0].normalized_value == 300_000.0
    assert claims[0].unit == "count"


def test_note_reference_is_not_promoted_as_a_hard_number() -> None:
    claims = extract_numeric_claims(
        "We repurchased 10 million shares. See Note 11 to the financial statements."
    )

    assert [item.raw_text for item in claims] == ["10 million"]


def test_dcf_assumptions_and_risk_coverage_map_to_their_own_metrics():
    markdown = (
        "The standardized reverse DCF implies a five-year FCF growth rate of "
        "19.9% at a 10% discount rate and 2% terminal growth.\n"
        "The base-case terminal value contributes 50% of equity value.\n"
        "The financial-risk screen has 100% financial-input coverage."
    )
    metrics = simple_metrics()
    scenarios = [
        ValuationScenario(
            name=name,
            starting_free_cash_flow=100,
            free_cash_flow_growth_rate=growth,
            discount_rate=discount,
            terminal_growth_rate=terminal,
            present_value_explicit_cash_flows=100,
            present_value_terminal_value=100,
            terminal_value_share=0.5,
            equity_value=200,
        )
        for name, growth, discount, terminal in (
            ("bear", 0.0, 0.12, 0.01),
            ("base", 0.05, 0.10, 0.02),
            ("bull", 0.10, 0.08, 0.03),
        )
    ]
    metrics.valuation.sensitivity = ValuationSensitivity(
        status="measured",
        reverse_dcf_implied_fcf_growth=0.199,
        scenarios=scenarios,
    )
    metrics.risk = IssuerRiskAssessment(
        status="partial",
        financial_risk_score=20,
        financial_risk_band="low_financial_risk",
        measured_weight=1,
        coverage_ratio=1,
    )

    claims = [claim for claim in extract_numeric_claims(markdown) if claim.unit == "percent"]
    assert {claim.raw_text: claim.possible_metric for claim in claims} == {
        "19.9%": "reverse_dcf_implied_fcf_growth",
        "10%": "dcf_base_discount_rate",
        "2%": "dcf_base_terminal_growth_rate",
        "50%": "dcf_base_terminal_value_share",
        "100%": "financial_risk_coverage",
    }

    audit = audit_markdown_report(markdown=markdown, metrics_packet=metrics)
    assert not any(issue.code == "NUMERIC_MISMATCH" for issue in audit.issues)

    distribution_claims = extract_numeric_claims(
        "TTM shareholder distributions are $97.87B; FCF exceeds shareholder "
        "distributions; the signed distributions-minus-FCF comparison is "
        "-$38.82B."
    )
    currency_claims = [item for item in distribution_claims if item.unit == "usd"]
    assert [item.normalized_value for item in currency_claims] == [
        97_870_000_000,
        -38_820_000_000,
    ]
    assert [item.possible_metric for item in currency_claims] == [
        "shareholder_distributions_ttm",
        "shareholder_distributions_minus_fcf_ttm",
    ]


def test_numeric_extractor_ignores_period_tokens_inside_evidence_metadata():
    claims = extract_numeric_claims(
        "Revenue TTM is 65.51B HUF. Evidence metrics: `revenue_ttm`. "
        "Evidence IDs: `ANY_REVENUE_FY2025_Q4`. Confidence: `high`."
    )
    claim = next(item for item in claims if item.unit == "huf")

    assert claim.period_hint == "ttm"
    assert "Q4" not in claim.nearby_text


def test_numeric_extractor_maps_each_adjacent_wm_anchor_to_its_own_metric():
    claims = extract_numeric_claims(
        "The available evidence anchors are revenue TTM of $25.67B, FCF TTM "
        "of $3.57B, EV/Sales of 4.42x."
    )

    assert [
        (claim.normalized_value, claim.possible_metric)
        for claim in claims
        if claim.unit == "usd"
    ] == [
        (25_670_000_000, "revenue_ttm"),
        (3_570_000_000, "free_cash_flow_ttm"),
    ]


def test_claim_bound_guidance_range_uses_uniquely_nearest_endpoint() -> None:
    low = 26_275_000_000.0
    high = 26_475_000_000.0
    claim = ResearchClaim(
        claim_id="WM_CLAIM_GUIDANCE",
        agent="deterministic_content_generator",
        claim="Revenue guidance is between $26.275 and $26.475 billion.",
        evidence_metrics=["guidance_revenue_low", "guidance_revenue_high"],
        metric_refs=["guidance_revenue_low", "guidance_revenue_high"],
        metric_values={"guidance_revenue_low": low, "guidance_revenue_high": high},
        evidence_ids=["WM_GUIDANCE_LOW", "WM_GUIDANCE_HIGH"],
        source_ids=["WM_SEC"],
        confidence="high",
    )
    ledger = EvidenceLedger(
        ticker="WM",
        as_of_date="2026-08-11",
        evidence_items=[
            EvidenceItem(
                evidence_id=evidence_id,
                ticker="WM",
                claim_type="guidance",
                source_id="WM_SEC",
                source_type="sec_filing",
                authority_rank=1,
                statement="Revenue guidance range.",
                value=value,
                unit="currency",
                currency="USD",
                dimension="currency",
                display_unit="USD",
                period_kind="guidance",
                period_start="2026-01-01",
                period_end="2026-12-31",
                date="2026-07-29",
                supports_metrics=[metric],
            )
            for evidence_id, value, metric in (
                ("WM_GUIDANCE_LOW", low, "guidance_revenue_low"),
                ("WM_GUIDANCE_HIGH", high, "guidance_revenue_high"),
            )
        ],
    )

    audit = audit_markdown_report(
        "Revenue guidance is between $26.275 and $26.475 billion. "
        "Claim `WM_CLAIM_GUIDANCE` · Evidence: `WM_GUIDANCE_LOW, WM_GUIDANCE_HIGH`.",
        simple_metrics(ticker="WM"),
        evidence_ledger=ledger,
        research_claims=[claim],
        ticker="WM",
    )
    guidance = [
        item for item in audit.numeric_claims
        if item.normalized_value in {low, high}
    ]

    assert [item.possible_metric for item in guidance] == [
        "guidance_revenue_low",
        "guidance_revenue_high",
    ]
    assert not audit.has_issue("NUMERIC_MISMATCH")


def test_direct_percent_evidence_normalizes_single_digit_percentage():
    metrics = simple_metrics(ticker="MCD")
    ledger = EvidenceLedger(
        ticker="MCD",
        as_of_date="2026-05-15",
        evidence_items=[
            EvidenceItem(
                evidence_id="MCD_CURRENT_REVENUE_GROWTH",
                ticker="MCD",
                claim_type="financial_metric",
                source_id="ROOM16_MCD_DETERMINISTIC_CALCULATIONS",
                source_type="deterministic_calculation",
                authority_rank=1,
                statement="Current-period revenue growth was 9.4%.",
                value=0.094,
                normalized_value=0.094,
                unit="percent",
                period="CY2025Q1..CY2026Q1",
                date="2026-03-31",
                supports_metrics=["current_period_revenue_growth_yoy"],
                formula_id="matching_quarter_yoy_growth",
                formula_operands={"current_revenue": 110.0, "prior_revenue": 100.0},
                confidence="high",
            )
        ],
    )

    audit = audit_markdown_report(
        markdown="Revenue changed by 9.4% against the matching prior-year quarter.",
        metrics_packet=metrics,
        evidence_ledger=ledger,
        ticker="MCD",
    )

    assert not audit.has_issue("NUMERIC_MISMATCH")


def test_current_ratio_threshold_is_not_mapped_to_rsi_or_a_reported_value():
    metrics = simple_metrics(ticker="GENERIC")
    metrics.fundamentals.current_ratio = 0.7714
    markdown = (
        "The current ratio is 0.77x. A current ratio below 1.0x is material "
        "liquidity context; assess cash conversion and debt maturities together."
    )

    claims = [
        claim
        for claim in extract_numeric_claims(markdown)
        if claim.unit == "multiple"
    ]
    audit = audit_markdown_report(markdown, metrics)

    assert [claim.possible_metric for claim in claims] == [
        "current_ratio",
        "current_ratio",
    ]
    assert not audit.has_issue("NUMERIC_MISMATCH")


def test_auditor_blocks_malformed_issuer_disclosure_fragments():
    malformed = [
        "Issuer-disclosed risk: us, our business could be adversely affected.",
        "Issuer-filed business context: We develop transformative medicines for.",
        "Issuer-disclosed risk: Our business could.",
        "Issuer-disclosed risk: Pricing pressure could harm our business,.",
    ]

    for markdown in malformed:
        audit = audit_markdown_report(
            markdown,
            simple_metrics(ticker="VRTX"),
            ticker="VRTX",
        )
        assert audit.has_blocking_errors is True
        assert audit.has_issue("MALFORMED_SEC_DISCLOSURE_FRAGMENT")


def test_auditor_blocks_additive_debt_and_lease_wording():
    audit = audit_markdown_report(
        "In addition to reported debt, separate lease liabilities total $1.25B.",
        simple_metrics(ticker="MDT"),
        ticker="MDT",
    )

    assert audit.has_blocking_errors is True
    assert audit.has_issue("LEASE_DEBT_DOUBLE_COUNT_RISK")


def test_auditor_requires_operating_kpi_for_material_insurance_business():
    markdown = (
        "Issuer-filed business context: The Health Care Benefits segment offers "
        "health insurance products and related services.\n"
        "Revenue and net income increased against the matching prior-year quarter."
    )

    audit = audit_markdown_report(markdown, simple_metrics(ticker="CVS"), ticker="CVS")

    assert audit.has_blocking_errors is True
    assert audit.has_issue("INSURER_OPERATING_KPI_CONTEXT_REQUIRED")


def test_auditor_accepts_validated_insurer_operating_kpi_context():
    markdown = (
        "Issuer-filed business context: The Health Care Benefits segment offers "
        "health insurance products and related services.\n"
        "The validated evidence includes the medical benefit ratio for the period."
    )

    registry = SourceRegistry(
        registry_id="CVS_2026_07_31",
        sources=[
            SourceRegistryEntry(
                source_id="CVS_SEC_INSURANCE_KPI",
                ticker="CVS",
                source_type="sec_filing",
                used_for=["medical_benefit_ratio"],
            )
        ],
    )
    audit = audit_markdown_report(
        markdown,
        simple_metrics(ticker="CVS"),
        ticker="CVS",
        source_registry=registry,
    )

    assert not audit.has_issue("INSURER_OPERATING_KPI_CONTEXT_REQUIRED")


def test_auditor_maps_each_matching_quarter_percentage_to_nearest_growth_metric():
    metrics = simple_metrics(ticker="GENERIC")
    metrics.fundamentals.current_period_revenue_growth_yoy = -0.014
    metrics.fundamentals.current_period_operating_income_growth_yoy = 0.048
    metrics.fundamentals.current_period_net_income_growth_yoy = 0.872
    markdown = (
        "Against the matching prior-year quarter, revenue declined by 1.4%, "
        "operating income increased by 4.8% and net income increased by 87.2%.\n"
        "Matching-quarter evidence reports revenue decline 1.4%, "
        "operating-income growth 4.8%, net-income growth 87.2%."
    )

    percent_claims = [
        claim for claim in extract_numeric_claims(markdown)
        if claim.unit == "percent"
    ]
    audit = audit_markdown_report(markdown, metrics)

    assert [claim.possible_metric for claim in percent_claims] == [
        "current_period_revenue_growth_yoy",
        "current_period_operating_income_growth_yoy",
        "current_period_net_income_growth_yoy",
        "current_period_revenue_growth_yoy",
        "current_period_operating_income_growth_yoy",
        "current_period_net_income_growth_yoy",
    ]
    assert not audit.has_issue("NUMERIC_MISMATCH")


def test_auditor_blocks_direction_from_unbenchmarked_valuation():
    metrics = simple_metrics(ticker="GENERIC")
    decision = build_decision_packet(metrics)

    audit = audit_markdown_report(
        markdown=(
            "Final Rating: Hold. EV/Sales of 118.78x argues against chasing "
            "the stock."
        ),
        metrics_packet=metrics,
        decision_packet=decision,
        ticker="GENERIC",
    )

    assert decision.signal_scores.valuation_status == "unbenchmarked"
    assert audit.has_issue("UNBENCHMARKED_VALUATION_DIRECTION")
    assert audit.has_blocking_errors


def test_auditor_accepts_neutral_unbenchmarked_valuation_observation():
    metrics = simple_metrics(ticker="GENERIC")
    decision = build_decision_packet(metrics)

    audit = audit_markdown_report(
        markdown=(
            "Final Rating: Hold. EV/Sales of 118.78x is an unbenchmarked "
            "observation and adds neither a positive nor a negative rating signal."
        ),
        metrics_packet=metrics,
        decision_packet=decision,
        ticker="GENERIC",
    )
    neutral_label = audit_markdown_report(
        markdown=(
            "Final Rating: Hold. P/FCF is 118.78x. This records the valuation "
            "level without labeling it cheap or expensive."
        ),
        metrics_packet=metrics,
        decision_packet=decision,
        ticker="GENERIC",
    )

    assert not audit.has_issue("UNBENCHMARKED_VALUATION_DIRECTION")
    assert not neutral_label.has_issue("UNBENCHMARKED_VALUATION_DIRECTION")


def test_auditor_blocks_false_missingness_when_trailing_pe_is_measured():
    metrics = simple_metrics(ticker="GENERIC")
    metrics.valuation.ev_to_sales = None
    metrics.valuation.trailing_pe = 7.68
    decision = build_decision_packet(metrics)

    audit = audit_markdown_report(
        markdown=(
            "Final Rating: Hold. No measured valuation multiple is available; "
            "unbenchmarked valuation cannot move the rating."
        ),
        metrics_packet=metrics,
        decision_packet=decision,
        ticker="GENERIC",
    )

    assert audit.has_issue("MEASURED_VALUATION_MISSINGNESS_CONTRADICTION")
    assert audit.has_blocking_errors


def test_auditor_blocks_currency_that_conflicts_with_evidence_ledger():
    metrics = simple_metrics(ticker="ANY", revenue_ttm=65_510_000_000)
    ledger = EvidenceLedger(
        ticker="ANY",
        as_of_date="2026-05-15",
        evidence_items=[
            EvidenceItem(
                evidence_id="ANY_REVENUE",
                ticker="ANY",
                claim_type="financial_metric",
                source_id="BSE_ANY_FINANCIALS",
                source_type="company_ir",
                authority_rank=1,
                statement="Revenue was reported in HUF.",
                value=65_510_000_000,
                unit="HUF",
                supports_metrics=["revenue_ttm"],
            )
        ],
    )

    wrong = audit_markdown_report(
        "Revenue TTM is $65.51B.",
        metrics,
        evidence_ledger=ledger,
    )
    correct = audit_markdown_report(
        "Revenue TTM is 65.51B HUF.",
        metrics,
        evidence_ledger=ledger,
    )

    assert wrong.has_issue("CURRENCY_MISMATCH", metric="revenue_ttm")
    assert wrong.has_blocking_errors
    assert not correct.has_issue("CURRENCY_MISMATCH")
    assert not correct.has_issue("NUMERIC_MISMATCH", metric="revenue_ttm")


def test_auditor_compares_net_debt_with_the_signed_net_cash_position():
    metrics = simple_metrics(ticker="ANY")
    metrics.fundamentals.net_cash = -4_610_000_000

    correct = audit_markdown_report("Net debt is 4.61B HUF.", metrics)
    wrong_amount = audit_markdown_report("Net debt is 3.00B HUF.", metrics)

    metrics.fundamentals.net_cash = 4_610_000_000
    false_debt = audit_markdown_report("Net debt is 4.61B HUF.", metrics)

    assert not correct.has_issue("NUMERIC_MISMATCH", metric="net_debt")
    assert wrong_amount.has_issue("NUMERIC_MISMATCH", metric="net_debt")
    assert false_debt.has_issue("NUMERIC_MISMATCH", metric="net_debt")


def test_auditor_blocks_stale_latest_period_cash_flow_pair():
    def cashflow_metric(metric_name, value, start_date, end_date, period):
        return CanonicalMetric(
            metric_name=metric_name,
            value=value,
            unit="USD",
            period=period,
            fiscal_year=2026,
            fiscal_period="Q1" if period == "CY2026Q1" else "Q3",
            period_bucket="quarterly" if period == "CY2026Q1" else "ytd",
            start_date=start_date,
            end_date=end_date,
            basis="gaap",
            statement_type="cash_flow",
            source_ids=[f"SEC_{period}"],
            confidence="high",
        )

    canonical = CanonicalFinancials(
        ticker="KMB",
        as_of_date="2026-08-03",
        metrics=[
            cashflow_metric(
                "operating_cash_flow",
                1_800_000_000,
                "2025-01-01",
                "2025-09-30",
                "Q3_FY2025_ytd",
            ),
            cashflow_metric(
                "capex",
                741_000_000,
                "2025-01-01",
                "2025-09-30",
                "Q3_FY2025_ytd",
            ),
            cashflow_metric(
                "operating_cash_flow",
                745_000_000,
                "2026-01-01",
                "2026-03-31",
                "CY2026Q1",
            ),
            cashflow_metric(
                "capex",
                424_000_000,
                "2026-01-01",
                "2026-03-31",
                "CY2026Q1",
            ),
        ],
    )
    stale = audit_markdown_report(
        "For the latest reported period (year to date), KMB generated $1.80B "
        "of operating cash flow and reported $741.0M of capital expenditure.",
        simple_metrics(ticker="KMB"),
        canonical_financials=canonical,
    )
    current = audit_markdown_report(
        "For the latest reported period (year to date), KMB generated $745.0M "
        "of operating cash flow and reported $424.0M of capital expenditure.",
        simple_metrics(ticker="KMB"),
        canonical_financials=canonical,
    )

    assert stale.has_issue(
        "CURRENT_PERIOD_CASH_FLOW_MISMATCH",
        metric="operating_cash_flow",
    )
    assert stale.has_issue("CURRENT_PERIOD_CASH_FLOW_MISMATCH", metric="capex")
    assert stale.has_blocking_errors
    assert not current.has_issue("CURRENT_PERIOD_CASH_FLOW_MISMATCH")


def test_auditor_recognizes_sec_exhibit_as_primary_issuer_fcf_source():
    metrics = simple_metrics(ticker="WM")
    metrics.fundamentals.free_cash_flow_ttm = 3_570_000_000
    canonical = CanonicalFinancials(
        ticker="WM",
        as_of_date="2026-08-11",
        metrics=[
            CanonicalMetric(
                metric_name="free_cash_flow",
                value=2_024_000_000,
                unit="USD",
                period="FY2026_YTD",
                period_bucket="ytd",
                start_date="2026-01-01",
                end_date="2026-06-30",
                basis="non_gaap",
                statement_type="cash_flow",
                source_ids=["SEC_CIK0000823768_EX99_1"],
                confidence="high",
            )
        ],
    )

    audit = audit_markdown_report(
        "## Executive Summary\nRoom16 normalized FCF TTM is $3.57B.",
        metrics,
        canonical_financials=canonical,
        ticker="WM",
    )

    assert audit.has_issue("COMPANY_DEFINED_FCF_MISMATCH")


def test_auditor_catches_nvda_fcf_ttm_mismatch():
    audit = audit_fixture("nvda_2026_05_01")

    assert audit.has_issue("NUMERIC_MISMATCH", metric="free_cash_flow_ttm")


def test_auditor_catches_q4_margin_labeled_as_ttm():
    audit = audit_fixture("nvda_2026_05_01")

    assert audit.has_issue("PERIOD_MISMATCH", metric="operating_margin")


def test_auditor_normalizes_large_percent_ratios():
    metrics = MetricsPacket(**load_fixture("mdb_2026_05_01", "metrics_packet.json"))
    metrics.fundamentals.sbc_to_revenue = 2.614

    audit = audit_markdown_report("SBC / Revenue: 261.4%.", metrics)

    assert not audit.has_issue("NUMERIC_MISMATCH", metric="sbc_to_revenue")


def test_auditor_maps_sbc_percent_of_fcf_to_ratio_not_fcf_amount():
    metrics = simple_metrics(ticker="KO")
    metrics.fundamentals.free_cash_flow_ttm = 14_297_000_000
    metrics.fundamentals.sbc_to_fcf = 0.0186053

    audit = audit_markdown_report(
        "FCF TTM is $14.30B. SBC equals 1.9% of that FCF.",
        metrics,
    )

    assert not audit.has_issue("NUMERIC_MISMATCH", metric="free_cash_flow_ttm")
    assert not audit.has_issue("NUMERIC_MISMATCH", metric="sbc_to_fcf")


def test_auditor_separates_sbc_ratio_from_share_count_change_in_same_claim():
    metrics = simple_metrics(ticker="AVGO")
    metrics.fundamentals.sbc_to_revenue = 0.1164115815278606
    metrics.fundamentals.diluted_share_count_yoy = 0.01036

    audit = audit_markdown_report(
        "SBC/Revenue is 11.6%. The diluted weighted-average share count "
        "increased by 1.0% against the matching prior-year period.",
        metrics,
    )

    assert not audit.has_issue("NUMERIC_MISMATCH", metric="sbc_to_revenue")
    assert not audit.has_issue(
        "NUMERIC_MISMATCH", metric="diluted_share_count_yoy"
    )


def test_auditor_treats_clean_sbc_over_revenue_as_true_anomaly_not_period_bug():
    metrics = simple_metrics(ticker="IONQ", revenue_ttm=132_800_000, market_cap=17_600_000_000, enterprise_value=17_580_000_000, ev_to_sales=132.41)
    metrics.fundamentals.sbc_to_revenue = 1.462

    audit = audit_markdown_report("## Executive Summary\nSBC/Revenue is extreme and must stay under review.", metrics, ticker="IONQ")

    assert audit.has_issue("TRUE_FINANCIAL_ANOMALY", metric="sbc_to_revenue")
    assert not audit.has_issue("PERIOD_DENOMINATOR_BUG", metric="sbc_to_revenue")


def test_auditor_flags_absurd_ev_sales_as_extreme_valuation_review():
    metrics = simple_metrics(
        ticker="NVDA",
        revenue_ttm=1_000_000_000,
        market_cap=450_000_000_000,
        enterprise_value=435_860_000_000,
        ev_to_sales=435.86,
    )

    audit = audit_markdown_report("## Executive Summary\nValidated skeleton.", metrics, ticker="NVDA")

    assert audit.has_issue("EXTREME_VALUATION_REQUIRES_REVIEW", metric="ev_to_sales")


def test_auditor_classifies_clean_rklb_extreme_ev_sales_as_review_not_period_bug():
    metrics = simple_metrics()

    audit = audit_markdown_report(
        "## Executive Summary\nBacklog and revenue growth partly support the valuation, but FCF remains negative.",
        metrics,
        source_registry=valuation_source_registry(),
        ticker="RKLB",
    )

    assert audit.has_issue("EXTREME_VALUATION_REQUIRES_REVIEW", metric="ev_to_sales")
    assert not audit.has_issue("PERIOD_DENOMINATOR_BUG", metric="ev_to_sales")
    assert not audit.has_issue("PERIOD_DENOMINATOR_BUG", metric="market_cap_to_revenue")


def test_auditor_keeps_period_denominator_bug_for_quarterly_revenue_bucket():
    metrics = simple_metrics(
        revenue_ttm=200_348_000,
        market_cap=24_314_000_000,
        enterprise_value=23_800_000_000,
        ev_to_sales=118.79327670378641,
    )
    canonical = CanonicalFinancials(
        ticker="RKLB",
        as_of_date="2026-05-15",
        metrics=[
            CanonicalMetric(
                metric_name="revenue",
                value=200_348_000,
                unit="usd",
                period="Q1_FY2026_quarterly",
                period_bucket="quarterly",
                duration_days=90,
                basis="gaap",
                statement_type="income_statement",
                source_ids=["RKLB_Q1_2026_IR"],
                confidence="high",
            )
        ],
    )

    audit = audit_markdown_report(
        "## Executive Summary\nValidated skeleton.",
        metrics,
        source_registry=valuation_source_registry(),
        canonical_financials=canonical,
        ticker="RKLB",
    )

    assert audit.has_issue("PERIOD_DENOMINATOR_BUG", metric="ev_to_sales")
    assert not audit.has_issue("EXTREME_VALUATION_REQUIRES_REVIEW", metric="ev_to_sales")


def test_auditor_does_not_flag_clean_mega_cap_ev_sales_below_30_as_valuation_anomaly():
    metrics = simple_metrics(
        ticker="MSFT",
        revenue_ttm=260_000_000_000,
        market_cap=3_100_000_000_000,
        enterprise_value=3_050_000_000_000,
        ev_to_sales=11.73,
    )

    audit = audit_markdown_report("## Executive Summary\nValidated skeleton.", metrics, ticker="MSFT")

    assert not audit.has_issue("EXTREME_VALUATION_REQUIRES_REVIEW", metric="ev_to_sales")
    assert not audit.has_issue("TRUE_VALUATION_ANOMALY", metric="ev_to_sales")
    assert not audit.has_issue("PERIOD_DENOMINATOR_BUG", metric="ev_to_sales")


def test_auditor_keeps_high_fcf_margin_as_one_non_blocking_context_review():
    metrics = MetricsPacket(**load_fixture("amzn_2026_05_01", "metrics_packet.json"))
    metrics.fundamentals.fcf_margin_ttm = 0.50

    audit = audit_markdown_report("## Executive Summary\nValidated skeleton.", metrics, ticker="AMZN")

    margin_issues = [issue for issue in audit.issues if issue.metric == "fcf_margin_ttm"]

    assert len(margin_issues) == 1
    assert margin_issues[0].code == "GUARD_THRESHOLD_REVIEW"
    assert margin_issues[0].severity == "warning"
    assert "mega_cap_tech context" in margin_issues[0].message
    assert not audit.has_blocking_errors


def test_auditor_requires_context_for_extreme_profit_revenue_divergence():
    metrics = simple_metrics(
        ticker="BASE",
        revenue_ttm=100_000_000_000,
        market_cap=190_000_000_000,
        enterprise_value=233_000_000_000,
        ev_to_sales=2.33,
    )
    metrics.fundamentals.current_period_revenue_growth_yoy = -0.014
    metrics.fundamentals.current_period_operating_income_growth_yoy = 0.048
    metrics.fundamentals.current_period_net_income_growth_yoy = 0.872

    audit = audit_markdown_report(
        "## Executive Summary\nValidated skeleton.",
        metrics,
        ticker="BASE",
    )
    growth_issues = [
        issue
        for issue in audit.issues
        if issue.metric == "current_period_net_income_growth_yoy"
    ]

    assert len(growth_issues) == 1
    assert growth_issues[0].code == "GUARD_THRESHOLD_REVIEW"
    assert growth_issues[0].severity == "warning"
    assert "at least 75%" in growth_issues[0].message
    assert "base effects" in growth_issues[0].message
    assert not audit.has_blocking_errors


def test_auditor_reviews_extreme_negative_profit_revenue_divergence():
    metrics = simple_metrics(ticker="BASE")
    metrics.fundamentals.current_period_revenue_growth_yoy = -0.012
    metrics.fundamentals.current_period_operating_income_growth_yoy = -0.139
    metrics.fundamentals.current_period_net_income_growth_yoy = -0.683

    audit = audit_markdown_report(
        "## Executive Summary\nValidated skeleton.",
        metrics,
        ticker="BASE",
    )
    issues = [
        issue
        for issue in audit.issues
        if issue.metric == "current_period_net_income_growth_yoy"
    ]

    assert len(issues) == 1
    assert issues[0].code == "GUARD_THRESHOLD_REVIEW"
    assert issues[0].severity == "warning"
    assert "Profit decline of at least 50%" in issues[0].message


def test_auditor_catches_long_stop_above_entry_in_markdown():
    audit = audit_fixture("ddog_2026_05_01")

    assert audit.has_issue("INVALID_TRADE_LEVEL")


def test_auditor_catches_overstated_news_causality():
    audit = audit_fixture("mdb_2026_05_01")

    assert audit.has_issue("OVERSTATED_CAUSALITY")


def test_auditor_does_not_join_unrelated_causality_and_price_sentences():
    audit = audit_markdown_report(
        """
## Data / Source Quality Note
- Price basis: 2026-08-04 official exchange close.

## Risks
Pricing regulations could change due to factors beyond management's control.
""",
        simple_metrics(ticker="BASE"),
        ticker="BASE",
    )

    assert not audit.has_issue("OVERSTATED_CAUSALITY")


def test_auditor_does_not_treat_operating_pricing_as_stock_price_causality():
    markdown = (
        "Collection revenue increased due to higher pricing and a favorable "
        "price-to-cost spread."
    )
    audit = audit_markdown_report(markdown, simple_metrics())

    assert not audit.has_issue("OVERSTATED_CAUSALITY")


def test_auditor_catches_forward_eps_guidance_mismatch():
    audit = audit_fixture("mdb_2026_05_01")

    assert audit.has_issue("FORWARD_EPS_GUIDANCE_MISMATCH")


def test_auditor_catches_sell_when_actions_are_trim():
    audit = audit_fixture("mdb_2026_05_01")

    assert audit.has_issue("RATING_TOO_HARSH_FOR_ACTION")


@pytest.mark.parametrize(
    "fixture_name",
    [
        "nvda_2026_05_01",
        "ddog_2026_05_01",
        "mdb_2026_05_01",
        "amzn_2026_05_01",
    ],
)
def test_golden_fixture_expected_audit_issues_are_found(fixture_name):
    audit = audit_fixture(fixture_name)
    expected = load_fixture(fixture_name, "expected_audit_issues.json")

    for issue in expected:
        assert audit.has_issue(issue["code"], metric=issue.get("metric"))


def test_auditor_catches_no_news_when_sources_exist():
    audit = audit_fixture("amzn_2026_05_01")

    assert audit.has_issue("NO_NEWS_WITH_AVAILABLE_SOURCES")


def test_report_linter_cli_runs_against_fixture():
    fixture_dir = FIXTURES / "amzn_2026_05_01"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_agent.audit.report_linter",
            "--report",
            str(fixture_dir / "bad_report.md"),
            "--metrics",
            str(fixture_dir / "metrics_packet.json"),
            "--validation",
            str(fixture_dir / "validation_report.json"),
            "--sources",
            str(fixture_dir / "source_registry.json"),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 2
    assert "NO_NEWS_WITH_AVAILABLE_SOURCES" in result.stdout


def test_report_builder_optional_audit_saves_failed_draft(tmp_path):
    data_packet = DataPacket(
        ticker="NVDA",
        company_name="NVIDIA Corporation",
        as_of_date="2026-05-01",
        price_basis=PriceBasis(close=900, date="2026-04-30", source="exchange_ohlcv"),
        fiscal_context=FiscalContext(),
        next_events=EventInfo(next_earnings_date="2026-05-21", confirmed=True, source="company_ir"),
        source_registry_id="NVDA_2026_05_01",
    )
    metrics_packet = MetricsPacket(
        ticker="NVDA",
        as_of_date="2026-05-01",
        technical=TechnicalMetrics(indicator_date="2026-04-30", close=900),
        fundamentals=FundamentalMetrics(fiscal_period="FY2026", free_cash_flow_ttm=96575000000),
        valuation=ValuationMetrics(),
    )
    validation_report = ValidationReport(
        ticker="NVDA",
        as_of_date="2026-05-01",
        has_blocking_errors=False,
        issues=[],
    )
    claims = [
        ResearchClaim(
            agent="fundamental",
            claim="FCF TTM is $58.1B.",
            evidence_metrics=["free_cash_flow_ttm"],
            source_ids=["NVDA_IR_FY2026"],
            confidence="high",
        )
    ]

    with pytest.raises(RuntimeError):
        render_markdown_report(
            data_packet,
            metrics_packet,
            validation_report,
            claims=claims,
            run_audit=True,
            audit_output_dir=str(tmp_path),
        )

    assert (tmp_path / "draft_failed_audit.md").exists()
    assert (tmp_path / "audit_report.json").exists()
