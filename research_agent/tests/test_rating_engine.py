from research_agent.decision.decision_packet import SignalScores
from research_agent.decision.rating_engine import build_decision_packet, determine_rating_permission
from research_agent.decision.rating_taxonomy import Rating
from research_agent.decision.signal_scores import (
    calculate_signal_scores,
    score_fundamentals,
    score_risk,
    score_technicals,
    score_valuation,
)
from research_agent.research_core.models.metrics_packet import (
    FundamentalMetrics,
    MetricsPacket,
    TechnicalMetrics,
    ValuationMetrics,
    ValuationScenario,
    ValuationSensitivity,
)
from research_agent.research_core.models.validation_report import ValidationReport


def _strong_metrics():
    return MetricsPacket(
        ticker="TEST",
        as_of_date="2026-05-01",
        technical=TechnicalMetrics(
            indicator_date="2026-04-30",
            close=100,
            sma_50=95,
            sma_200=90,
            ema_10=98,
            rsi_14=55,
            macd_histogram=1,
            atr_14=3,
            price_series_basis="corporate_action_adjusted",
        ),
        fundamentals=FundamentalMetrics(
            fiscal_period="FY2026",
            revenue_growth_yoy=0.35,
            free_cash_flow_ttm=100,
            fcf_margin_ttm=0.30,
            operating_margin_ttm=0.20,
            sbc_to_revenue=0.05,
            net_cash=50,
        ),
        valuation=ValuationMetrics(
            forward_pe_consensus=24,
            price_to_fcf=25,
            peg_ratio=0.8,
        ),
    )


def test_fundamentals_use_directional_evidence_not_global_quality_thresholds():
    metrics = _strong_metrics()
    packet = build_decision_packet(metrics)

    assert score_fundamentals(metrics) == 1
    assert score_technicals(metrics) == 1
    assert score_valuation(metrics) == 0
    assert score_risk(metrics) == 0
    assert packet.signal_scores.valuation_status == "unbenchmarked"
    unbenchmarked_permission = determine_rating_permission(
        SignalScores(
            fundamental_score=3,
            technical_score=3,
            valuation_score=0,
            risk_score=0,
            composite_score=3,
            valuation_status="unbenchmarked",
        )
    )
    assert unbenchmarked_permission.evidence_status == "partial"
    assert unbenchmarked_permission.allowed_ratings == [Rating.HOLD]
    assert not any(
        rule.startswith(
            (
                "REVENUE_GROWTH_",
                "FCF_MARGIN_GT_",
                "OPERATING_MARGIN_GT_",
                "NET_CASH_",
                "FORWARD_PE_",
                "PRICE_TO_FCF_",
                "PEG_",
                "SBC_TO_",
                "PRICE_ABOVE_",
                "PRICE_BELOW_",
                "BULLISH_MA_",
                "BEARISH_MA_",
                "GOLDEN_CROSS",
                "DEATH_CROSS",
                "RSI_",
                "MACD_",
                "ATR_PCT_",
            )
        )
        for rule in packet.triggered_rules
    )
    assert "TREND_STATE_BULLISH" in packet.triggered_rules


def _standardized_dcf_sensitivity(*, equity_value: float) -> ValuationSensitivity:
    scenarios = []
    for name, growth, discount, terminal in (
        ("bear", -0.05, 0.12, 0.01),
        ("base", 0.05, 0.10, 0.02),
        ("bull", 0.15, 0.08, 0.03),
    ):
        scenarios.append(
            ValuationScenario(
                name=name,
                starting_free_cash_flow=100.0,
                free_cash_flow_growth_rate=growth,
                discount_rate=discount,
                terminal_growth_rate=terminal,
                present_value_explicit_cash_flows=equity_value * 0.25,
                present_value_terminal_value=equity_value * 0.75,
                terminal_value_share=0.75,
                equity_value=equity_value,
            )
        )
    return ValuationSensitivity(
        status="measured",
        current_market_cap=1_000.0,
        current_price=100.0,
        share_basis="listed_share_count",
        reverse_dcf_implied_fcf_growth=0.20,
        reverse_dcf_status="measured",
        model_range_low=equity_value,
        model_range_base=equity_value,
        model_range_high=equity_value,
        current_value_position="inside_range",
        scenarios=scenarios,
        limitations=["standardized sensitivity; not calibrated fair value"],
    )


def test_standardized_dcf_extremes_cannot_change_rating_without_calibration():
    deeply_bearish = _strong_metrics()
    deeply_bearish.fundamentals.revenue_ttm = 1_000.0
    deeply_bearish.fundamentals.operating_income_ttm = 200.0
    deeply_bearish.fundamentals.net_income_ttm = 150.0
    deeply_bearish.fundamentals.operating_cash_flow_ttm = 120.0
    deeply_bearish.fundamentals.total_debt = 50.0
    deeply_bearish.valuation.sensitivity = _standardized_dcf_sensitivity(
        equity_value=100.0
    )

    deeply_bullish = deeply_bearish.model_copy(deep=True)
    deeply_bullish.valuation.sensitivity = _standardized_dcf_sensitivity(
        equity_value=10_000.0
    )

    bearish_packet = build_decision_packet(deeply_bearish)
    bullish_packet = build_decision_packet(deeply_bullish)

    assert bearish_packet.signal_scores.valuation_status == "scenario_measured"
    assert bullish_packet.signal_scores.valuation_status == "scenario_measured"
    assert bearish_packet.signal_scores.valuation_score == 0
    assert bullish_packet.signal_scores.valuation_score == 0
    assert (
        bearish_packet.signal_scores.composite_score
        == bullish_packet.signal_scores.composite_score
    )
    assert (
        bearish_packet.rating_permission.preferred_rating
        == bullish_packet.rating_permission.preferred_rating
        == Rating.HOLD
    )
    assert bearish_packet.conclusion_status == "provisional"
    assert bullish_packet.conclusion_status == "provisional"
    assert "without calibrated valuation evidence" in (
        bearish_packet.analytical_rating_reason or ""
    )
    assert "without calibrated valuation evidence" in (
        bullish_packet.analytical_rating_reason or ""
    )
    assert not any("DCF" in rule for rule in bearish_packet.triggered_rules)
    assert not any("DCF" in rule for rule in bullish_packet.triggered_rules)


def test_momentum_and_volatility_observations_do_not_stack_rating_scores():
    metrics = _strong_metrics()
    metrics.technical.rsi_14 = 90
    metrics.technical.atr_14 = 20
    metrics.technical.ema_10 = 120
    metrics.technical.macd_histogram = -10
    packet = build_decision_packet(metrics)

    assert packet.signal_scores.technical_score == 1
    assert packet.signal_scores.risk_score == 0
    assert packet.signal_scores.risk_status == "not_measured"
    assert packet.triggered_rules == [
        "FCF_TTM_POSITIVE",
        "TREND_STATE_BULLISH",
    ]


def test_unadjusted_price_series_cannot_create_technical_score_or_rule():
    metrics = _strong_metrics()
    metrics.technical.price_series_basis = "unadjusted_or_provider_default"

    packet = build_decision_packet(metrics)

    assert packet.signal_scores.technical_score == 0
    assert packet.signal_scores.technical_status == "partial"
    assert "TREND_STATE_BULLISH" not in packet.triggered_rules
    assert "risk_markers" not in packet.action_policy
    assert "technical_boundary" in packet.action_policy
    assert "zero is not a low-risk conclusion" in packet.key_reasons[-1]


def test_non_positive_equity_offsets_positive_fcf_without_inventing_a_ratio():
    metrics = _strong_metrics()
    metrics.fundamentals.equity = -7_674_300_000

    packet = build_decision_packet(metrics)

    assert score_fundamentals(metrics) == 0
    assert packet.signal_scores.fundamental_score == 0
    assert packet.signal_scores.composite_score == 0
    assert packet.triggered_rules == [
        "FCF_TTM_POSITIVE",
        "EQUITY_NON_POSITIVE",
        "TREND_STATE_BULLISH",
    ]


def test_unbenchmarked_strong_setup_is_capped_at_hold():
    packet = build_decision_packet(_strong_metrics())

    assert packet.analytical_rating_unconstrained is None
    assert packet.rating_permission.preferred_rating == Rating.HOLD
    assert packet.conclusion_status == "not_rated"
    assert "incomplete" in packet.conclusion_status_reason
    assert packet.evidence_maturity == "incomplete"
    assert packet.publication_permission == "blocked"
    assert packet.rating_permission.permission_type == "safety_fallback"
    assert packet.rating_permission.display_rating == "Unrated"
    assert packet.rating_permission.publication_allowed is False
    assert packet.rating_permission.fallback_only is True
    assert packet.action_policy["actionability"] == "blocked"
    assert packet.action_policy["internal_fallback_rating"] == "Hold"
    assert Rating.ACCUMULATE in packet.rating_permission.blocked_ratings
    assert Rating.STRONG_BUY in packet.rating_permission.blocked_ratings
    assert Rating.SELL in packet.rating_permission.blocked_ratings

    negative_permission = determine_rating_permission(
        SignalScores(
            fundamental_score=-2,
            technical_score=-1,
            valuation_score=0,
            risk_score=-3,
            composite_score=-3,
            valuation_status="unbenchmarked",
            risk_status="partial",
        )
    )
    assert negative_permission.preferred_rating == Rating.UNDERWEIGHT
    assert negative_permission.allowed_ratings == [Rating.UNDERWEIGHT]
    assert Rating.SELL in negative_permission.blocked_ratings

    partial_negative_permission = determine_rating_permission(
        SignalScores(
            fundamental_score=-2,
            technical_score=-1,
            valuation_score=0,
            risk_score=0,
            composite_score=-3,
            fundamental_status="partial",
            technical_status="partial",
            valuation_status="unbenchmarked",
            risk_status="not_measured",
        )
    )
    assert partial_negative_permission.preferred_rating == Rating.HOLD
    assert partial_negative_permission.allowed_ratings == [Rating.HOLD]
    assert "Core fundamental coverage is incomplete" in partial_negative_permission.reason
    assert "excluded from rating and timing" in partial_negative_permission.reason

    partial_technical_permission = determine_rating_permission(
        SignalScores(
            fundamental_score=-1,
            technical_score=1,
            valuation_score=0,
            risk_score=0,
            composite_score=0,
            fundamental_status="measured",
            technical_status="partial",
            valuation_status="unbenchmarked",
            risk_status="not_measured",
        )
    )
    assert partial_technical_permission.preferred_rating == Rating.HOLD
    assert "neutral analytical stance" in partial_technical_permission.reason
    assert "excluded from rating and timing" in partial_technical_permission.reason


def test_validation_quality_cannot_change_the_company_rating():
    metrics = _strong_metrics()
    validation = ValidationReport(
        ticker="TEST",
        as_of_date="2026-05-01",
        has_blocking_errors=False,
        issues=[
            {
                "severity": "warning",
                "code": "FORWARD_EPS_GUIDANCE_MISMATCH",
                "message": "Gap.",
            }
        ],
    )
    scores = calculate_signal_scores(metrics, validation)
    permission = determine_rating_permission(
        scores,
        action_class="staged_entry",
        validation_report=validation,
    )

    assert permission.preferred_rating == Rating.HOLD
    assert permission.allowed_ratings == [Rating.HOLD]
    assert scores.risk_score == 0
    assert scores.risk_status == "not_measured"
    assert scores.composite_score == 1
    assert Rating.STRONG_BUY in permission.blocked_ratings
    assert Rating.ACCUMULATE in permission.blocked_ratings


def test_blocking_validation_marks_conclusion_blocked_without_rewriting_rating():
    validation = ValidationReport(
        ticker="TEST",
        as_of_date="2026-05-01",
        has_blocking_errors=True,
        issues=[],
    )

    packet = build_decision_packet(_strong_metrics(), validation_report=validation)

    assert packet.analytical_rating_unconstrained is None
    assert packet.conclusion_status == "blocked"
    assert "validation" in packet.conclusion_status_reason.lower()
    assert packet.rating_permission.display_rating == "Unrated"
    assert packet.publication_permission == "blocked"


def test_incomplete_research_scope_is_the_explicit_rating_blocker():
    packet = build_decision_packet(
        _strong_metrics(),
        research_scope_complete=False,
        research_scope_gaps=["transactions_and_financing"],
    )

    assert packet.conclusion_status == "not_rated"
    assert packet.analytical_rating_unconstrained is None
    assert packet.rating_permission.display_rating == "Unrated"
    assert packet.rating_permission.preferred_rating == Rating.HOLD
    assert packet.rating_permission.fallback_only is True
    assert "transactions_and_financing" in packet.conclusion_status_reason
