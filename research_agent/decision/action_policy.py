from __future__ import annotations

from research_agent.decision.rating_taxonomy import Rating
from research_agent.research_core.models.metrics_packet import MetricsPacket


def build_action_policy(preferred_rating: Rating, metrics: MetricsPacket) -> dict[str, object]:
    t = metrics.technical

    if preferred_rating == Rating.TACTICAL_TRIM:
        return {
            "primary_action": "Trim partial exposure",
            "trim_size": "20-30%",
            "hold_core": True,
            "reentry_conditions": [
                "Pullback to validated support zone",
                "Breakout above validated resistance with volume",
                "Positive earnings/guidance confirmation",
            ],
            "risk_controls": {
                "review_level": t.sma_50,
                "hard_stop_reference": t.bollinger_lower,
            },
        }

    if preferred_rating == Rating.ACCUMULATE:
        return {
            "primary_action": "Staged accumulation",
            "initial_position": "20-30%",
            "add_conditions": [
                "Pullback to support",
                "Reclaim of short-term moving average",
                "Positive fundamental catalyst",
            ],
            "risk_controls": {
                "stop_reference": t.sma_50 or t.bollinger_lower,
            },
        }

    if preferred_rating == Rating.HOLD:
        return {
            "primary_action": "Maintain existing position",
            "new_money": "Wait for confirmation or better entry",
            "risk_controls": {
                "review_level": t.sma_50,
                "hard_stop_reference": t.sma_200,
            },
        }

    if preferred_rating == Rating.TACTICAL_UNDERWEIGHT:
        return {
            "primary_action": "Temporarily stay below target exposure",
            "trim_size": "20-30%",
            "hold_core": True,
            "risk_controls": {
                "review_level": t.sma_50,
                "hard_stop_reference": t.sma_200 or t.bollinger_lower,
            },
        }

    return {
        "primary_action": "Manual review required",
    }

