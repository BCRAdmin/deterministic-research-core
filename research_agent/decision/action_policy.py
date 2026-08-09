from __future__ import annotations

from research_agent.decision.rating_taxonomy import Rating
from research_agent.research_core.models.metrics_packet import MetricsPacket


_TECHNICAL_POLICY_BASES = {
    "corporate_action_adjusted",
    "post_corporate_action_only",
}


def _with_technical_boundary(
    policy: dict[str, object],
    metrics: MetricsPacket,
    *,
    risk_markers: dict[str, object] | None = None,
    technical_confirmation_conditions: list[str] | None = None,
) -> dict[str, object]:
    if metrics.technical.price_series_basis in _TECHNICAL_POLICY_BASES:
        if technical_confirmation_conditions:
            existing = list(policy.get("confirmation_conditions") or [])
            policy["confirmation_conditions"] = [
                *technical_confirmation_conditions,
                *existing,
            ]
        if risk_markers:
            policy["risk_markers"] = {
                key: value for key, value in risk_markers.items() if value is not None
            }
        return policy
    policy["technical_boundary"] = (
        "Numeric timing levels are withheld because corporate-action adjustment "
        "of the price series is not confirmed."
    )
    return policy


def build_action_policy(preferred_rating: Rating, metrics: MetricsPacket) -> dict[str, object]:
    t = metrics.technical

    if preferred_rating == Rating.TACTICAL_TRIM:
        return _with_technical_boundary({
            "research_stance": "Cautious bias while timing or event risk remains elevated",
            "confirmation_conditions": [
                "Positive earnings/guidance confirmation",
            ],
        }, metrics, risk_markers={
                "review_level": t.sma_50,
                "downside_reference": t.bollinger_lower,
        }, technical_confirmation_conditions=[
            "Pullback to validated support zone",
            "Breakout above validated resistance with volume",
        ])

    if preferred_rating == Rating.ACCUMULATE:
        return _with_technical_boundary({
            "research_stance": "Constructive bias, conditional on staged confirmation",
            "confirmation_conditions": [
                "Positive fundamental catalyst",
            ],
        }, metrics, risk_markers={
                "downside_reference": t.sma_50 or t.bollinger_lower,
        }, technical_confirmation_conditions=[
            "Pullback to support",
            "Reclaim of short-term moving average",
        ])

    if preferred_rating == Rating.HOLD:
        return _with_technical_boundary({
            "research_stance": "Neutral bias pending stronger confirmation or a better risk/reward setup",
        }, metrics, risk_markers={
                "review_level": t.sma_50,
                "downside_reference": t.sma_200,
        })

    if preferred_rating == Rating.TACTICAL_UNDERWEIGHT:
        return _with_technical_boundary({
            "research_stance": "Defensive bias while risk/reward or event risk remains unfavorable",
        }, metrics, risk_markers={
                "review_level": t.sma_50,
                "downside_reference": t.sma_200 or t.bollinger_lower,
        })

    return {
        "research_stance": "Manual review required",
    }
