from research_agent.decision.action_policy import build_action_policy
from research_agent.decision.rating_taxonomy import Rating, RATING_DEFINITIONS
from research_agent.research_core.models.metrics_packet import (
    FundamentalMetrics,
    MetricsPacket,
    TechnicalMetrics,
    ValuationMetrics,
)


def _metrics() -> MetricsPacket:
    return MetricsPacket(
        ticker="GENR",
        as_of_date="2026-07-26",
        technical=TechnicalMetrics(
            indicator_date="2026-07-26",
            close=100.0,
            sma_50=95.0,
            sma_200=80.0,
            bollinger_lower=90.0,
            price_series_basis="corporate_action_adjusted",
        ),
        fundamentals=FundamentalMetrics(fiscal_period="FY2026"),
        valuation=ValuationMetrics(),
    )


def test_generated_policies_are_research_views_not_personal_position_instructions():
    forbidden_keys = {
        "primary_action",
        "trim_size",
        "initial_position",
        "new_money",
        "hold_core",
        "risk_controls",
    }

    for rating in Rating:
        policy = build_action_policy(rating, _metrics())
        assert policy.get("research_stance")
        assert forbidden_keys.isdisjoint(policy)
        assert "%" not in str(policy)

    accumulate = build_action_policy(Rating.ACCUMULATE, _metrics())
    assert "risk_markers" in accumulate
    assert "Pullback to support" in accumulate["confirmation_conditions"]


def test_rating_definitions_do_not_prescribe_personal_trades():
    forbidden_phrases = (
        "build position",
        "maintain existing position",
        "reduce partial exposure",
        "exit most",
        "do not initiate",
    )

    for definition in RATING_DEFINITIONS.values():
        normalized = definition.lower()
        assert all(phrase not in normalized for phrase in forbidden_phrases)


def test_unadjusted_series_withholds_numeric_policy_levels():
    metrics = _metrics()
    metrics.technical.price_series_basis = "unadjusted_or_provider_default"

    policy = build_action_policy(Rating.HOLD, metrics)

    assert "risk_markers" not in policy
    assert "technical_boundary" in policy
