import pytest

from research_agent.decision.rating_engine import build_decision_packet
from research_agent.evidence.evidence_item import EvidenceItem
from research_agent.research_core.calculations.issuer_risk import calculate_issuer_risk
from research_agent.research_core.calculations.valuation import (
    calculate_valuation_metrics,
    equity_dcf_value,
)
from research_agent.research_core.models.metrics_packet import (
    FundamentalMetrics,
    MetricsPacket,
    TechnicalMetrics,
)


def _ko_like_fundamentals(**updates):
    payload = {
        "fiscal_period": "TTM through FY2026_Q2",
        "revenue_growth_yoy": 0.0187,
        "revenue_ttm": 50_129_000_000,
        "operating_income_ttm": 14_854_000_000,
        "net_income_ttm": 14_316_000_000,
        "operating_cash_flow_ttm": 16_342_000_000,
        "free_cash_flow_ttm": 14_297_000_000,
        "fcf_margin_ttm": 0.2852,
        "free_cash_flow_conversion_ttm": 0.9987,
        "cash_and_equivalents": 12_907_000_000,
        "short_term_investments": 622_000_000,
        "marketable_securities": 2_842_000_000,
        "total_debt": 43_495_000_000,
        "net_cash": -27_124_000_000,
        "current_ratio": 1.3046,
        "debt_to_equity": 1.2032,
        "equity": 36_150_000_000,
        "free_cash_flow_interest_coverage_ttm": 9.1296,
        "listed_share_count": 4_302_482_418,
        "economic_share_count": 4_302_549_243,
        "trailing_eps": 3.18,
        "diluted_share_count_yoy": -0.00046,
        "sbc_to_revenue": 0.0053,
        "shareholder_distributions_ttm": 11_995_000_000,
        "shareholder_distributions_minus_fcf_ttm": -2_302_000_000,
    }
    payload.update(updates)
    return FundamentalMetrics(**payload)


def _risk_evidence(statement: str, index: int = 1) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=f"TEST_RISK_{index}",
        ticker="TEST",
        claim_type="risk",
        source_id="SEC_TEST",
        source_type="sec_filing",
        authority_rank=1,
        statement=statement,
    )


def test_equity_dcf_requires_positive_cash_flow_and_valid_terminal_assumptions():
    explicit, terminal, total = equity_dcf_value(
        100,
        free_cash_flow_growth_rate=0.05,
        discount_rate=0.10,
        terminal_growth_rate=0.02,
    )

    assert explicit > 0
    assert terminal > 0
    assert total == pytest.approx(explicit + terminal)
    with pytest.raises(ValueError):
        equity_dcf_value(0, 0.05, 0.10, 0.02)
    with pytest.raises(ValueError):
        equity_dcf_value(100, 0.05, 0.02, 0.02)


def test_valuation_sensitivity_is_measured_only_with_verified_share_basis():
    measured = calculate_valuation_metrics(86.83, _ko_like_fundamentals())
    illustrative = calculate_valuation_metrics(
        158.43,
        _ko_like_fundamentals(
            listed_share_count=None,
            economic_share_count=2_403_058_480,
            economic_share_count_basis="multi_class_unverified_price_equivalence",
        ),
    )

    assert measured.sensitivity.status == "measured"
    assert [scenario.name for scenario in measured.sensitivity.scenarios] == [
        "bear",
        "base",
        "bull",
    ]
    assert measured.sensitivity.model_range_low < measured.sensitivity.model_range_high
    assert measured.sensitivity.reverse_dcf_status == "measured"
    assert measured.sensitivity.reverse_dcf_implied_fcf_growth is not None
    assert measured.sensitivity.scenarios[1].implied_price is not None

    assert illustrative.market_cap is None
    assert illustrative.sensitivity.status == "illustrative_only"
    assert illustrative.sensitivity.reverse_dcf_status == (
        "illustrative_unverified_share_equivalence"
    )
    assert illustrative.sensitivity.scenarios[1].implied_price is None


def test_financial_risk_score_does_not_treat_disclosure_volume_as_severity():
    fundamentals = _ko_like_fundamentals()
    one_heading = calculate_issuer_risk(
        fundamentals,
        [_risk_evidence("Cybersecurity and personal data risks")],
    )
    many_headings = calculate_issuer_risk(
        fundamentals,
        [
            _risk_evidence("Cybersecurity and personal data risks", 1),
            _risk_evidence("Competition and artificial intelligence risks", 2),
            _risk_evidence("Regulatory compliance risks", 3),
        ],
    )

    assert one_heading.status == "partial"
    assert one_heading.financial_risk_score == many_headings.financial_risk_score
    assert one_heading.financial_risk_band == many_headings.financial_risk_band
    assert one_heading.disclosed_business_risk_categories == ["cyber_and_data"]
    assert set(many_headings.disclosed_business_risk_categories) == {
        "competition_and_technology",
        "cyber_and_data",
        "regulation_and_legal",
    }
    assert many_headings.qualitative_business_risk_status == "human_review_required"


def test_incomplete_financial_screen_never_claims_low_risk():
    assessment = calculate_issuer_risk(
        _ko_like_fundamentals(
            debt_to_equity=None,
            free_cash_flow_interest_coverage_ttm=None,
            operating_income_interest_coverage_ttm=None,
            shareholder_distributions_ttm=None,
            shareholder_distributions_minus_fcf_ttm=None,
        )
    )

    assert assessment.coverage_ratio < 1
    assert assessment.financial_risk_score is not None
    assert assessment.financial_risk_band == "incomplete_financial_screen"
    assert any("must not be described as a low-risk conclusion" in item for item in assessment.limitations)


def test_elevated_financial_risk_can_only_reduce_composite_score():
    fundamentals = _ko_like_fundamentals(
        equity=-1,
        current_ratio=0.7,
        debt_to_equity=3.0,
        free_cash_flow_interest_coverage_ttm=1.0,
        free_cash_flow_ttm=-1_000_000,
        fcf_margin_ttm=-0.05,
        free_cash_flow_conversion_ttm=-0.10,
        diluted_share_count_yoy=0.12,
        sbc_to_revenue=0.25,
        shareholder_distributions_ttm=1_000_000,
        shareholder_distributions_minus_fcf_ttm=2_000_000,
    )
    risk = calculate_issuer_risk(fundamentals)
    metrics = MetricsPacket(
        ticker="TEST",
        as_of_date="2026-08-05",
        technical=TechnicalMetrics(
            indicator_date="2026-08-05",
            close=10,
            sma_50=9,
            sma_200=8,
            price_series_basis="corporate_action_adjusted",
        ),
        fundamentals=fundamentals,
        valuation=calculate_valuation_metrics(10, fundamentals),
        risk=risk,
    )

    packet = build_decision_packet(metrics)

    assert risk.financial_risk_band == "high_financial_risk"
    assert packet.signal_scores.risk_score == -2
    assert packet.signal_scores.risk_status == "partial"
    assert packet.signal_scores.composite_score <= (
        packet.signal_scores.fundamental_score
        + packet.signal_scores.valuation_score
    )
    assert "Qualitative business-risk severity" in packet.key_risks[-1]


def test_technical_direction_is_excluded_from_long_term_composite():
    fundamentals = _ko_like_fundamentals()
    base = MetricsPacket(
        ticker="TEST",
        as_of_date="2026-08-05",
        technical=TechnicalMetrics(
            indicator_date="2026-08-05",
            close=10,
            sma_50=9,
            sma_200=8,
            price_series_basis="corporate_action_adjusted",
        ),
        fundamentals=fundamentals,
        valuation=calculate_valuation_metrics(10, fundamentals),
        risk=calculate_issuer_risk(fundamentals),
    )
    bullish = build_decision_packet(base)
    base.technical.sma_50 = 8
    base.technical.sma_200 = 9
    base.technical.close = 7
    bearish = build_decision_packet(base)

    assert bullish.signal_scores.technical_score == 1
    assert bearish.signal_scores.technical_score == -1
    assert bullish.signal_scores.composite_score == bearish.signal_scores.composite_score
    assert bullish.rating_permission.preferred_rating == bearish.rating_permission.preferred_rating
