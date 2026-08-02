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


def test_signal_scores_are_clamped_to_rating_scale():
    metrics = _strong_metrics()
    packet = build_decision_packet(metrics)

    assert score_fundamentals(metrics) == 3
    assert score_technicals(metrics) == 3
    assert score_valuation(metrics) == 0
    assert score_risk(metrics) == 0
    assert packet.signal_scores.valuation_status == "unbenchmarked"
    benchmark_permission = determine_rating_permission(
        SignalScores(
            fundamental_score=3,
            technical_score=3,
            valuation_score=0,
            risk_score=0,
            composite_score=3,
            valuation_status="unbenchmarked",
        )
    )
    assert benchmark_permission.evidence_status == "partial"
    assert not any(
        rule.startswith(("FORWARD_PE_", "PRICE_TO_FCF_", "PEG_", "SBC_TO_"))
        for rule in packet.triggered_rules
    )


def test_unbenchmarked_strong_setup_is_capped_at_hold():
    packet = build_decision_packet(_strong_metrics())

    assert packet.analytical_rating_unconstrained == Rating.HOLD
    assert packet.rating_permission.preferred_rating == Rating.HOLD
    assert Rating.ACCUMULATE in packet.rating_permission.blocked_ratings
    assert Rating.STRONG_BUY in packet.rating_permission.blocked_ratings
    assert Rating.SELL in packet.rating_permission.blocked_ratings


def test_material_validation_warnings_keep_strong_buy_blocked():
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
    permission = determine_rating_permission(scores, validation_report=validation)

    assert Rating.STRONG_BUY in permission.blocked_ratings
