from __future__ import annotations

from research_agent.decision.rating_taxonomy import Rating
from research_agent.research_core.models.metrics_packet import MetricsPacket


def build_action_policy(preferred_rating: Rating, metrics: MetricsPacket) -> dict[str, object]:
    t = metrics.technical

    if preferred_rating == Rating.TACTICAL_TRIM:
        return {
            "research_stance": "Cautious bias while timing or event risk remains elevated",
            "confirmation_conditions": [
                "Pullback to validated support zone",
                "Breakout above validated resistance with volume",
                "Positive earnings/guidance confirmation",
            ],
            "risk_markers": {
                "review_level": t.sma_50,
                "downside_reference": t.bollinger_lower,
            },
        }

    if preferred_rating == Rating.ACCUMULATE:
        return {
            "research_stance": "Constructive bias, conditional on staged confirmation",
            "confirmation_conditions": [
                "Pullback to support",
                "Reclaim of short-term moving average",
                "Positive fundamental catalyst",
            ],
            "risk_markers": {
                "downside_reference": t.sma_50 or t.bollinger_lower,
            },
        }

    if preferred_rating == Rating.HOLD:
        return {
            "research_stance": "Neutral bias pending stronger confirmation or a better risk/reward setup",
            "risk_markers": {
                "review_level": t.sma_50,
                "downside_reference": t.sma_200,
            },
        }

    if preferred_rating == Rating.TACTICAL_UNDERWEIGHT:
        return {
            "research_stance": "Defensive bias while risk/reward or event risk remains unfavorable",
            "risk_markers": {
                "review_level": t.sma_50,
                "downside_reference": t.sma_200 or t.bollinger_lower,
            },
        }

    return {
        "research_stance": "Manual review required",
    }
