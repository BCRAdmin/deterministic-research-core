from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from research_agent.outcomes.price_outcome import WindowOutcome


class ActionEvaluation(BaseModel):
    action_type: str
    success: Optional[bool]
    notes: list[str] = Field(default_factory=list)
    stop_was_hit: Optional[bool] = None
    target_was_hit: Optional[bool] = None
    pullback_entry_was_available: Optional[bool] = None
    breakout_confirmation_was_available: Optional[bool] = None


def evaluate_action_policy(
    action_policy: dict[str, object],
    outcome: WindowOutcome,
    pullback_threshold: float = -0.05,
    trim_drawdown_threshold: float = -0.08,
) -> ActionEvaluation:
    research_stance = str(
        action_policy.get("research_stance")
        or action_policy.get("primary_action")
        or "Manual review required"
    )
    normalized = research_stance.lower()
    notes: list[str] = []
    max_drawdown = outcome.max_drawdown_pct
    max_gain = outcome.max_gain_pct
    return_pct = outcome.return_pct

    pullback_available = max_drawdown is not None and max_drawdown <= pullback_threshold
    breakout_available = max_gain is not None and max_gain >= abs(pullback_threshold)

    if "constructive" in normalized or "staged" in normalized or "accumulation" in normalized:
        success = pullback_available and outcome.hit_stop is not True
        notes.append("A conditional constructive view is validated when a pullback appears without an immediate downside breach.")
        return _evaluation(research_stance, success, notes, outcome, pullback_available, breakout_available)

    if "cautious" in normalized or "defensive" in normalized or "trim" in normalized or "reduce" in normalized or "below target" in normalized:
        drawdown_confirmed = max_drawdown is not None and max_drawdown <= trim_drawdown_threshold
        weakness_confirmed = return_pct is not None and return_pct < 0
        success = drawdown_confirmed or weakness_confirmed
        notes.append("A cautious or defensive view is validated when later weakness confirms the risk signal.")
        return _evaluation(research_stance, success, notes, outcome, pullback_available, breakout_available)

    if "neutral" in normalized or "maintain" in normalized or "hold" in normalized:
        success = return_pct is not None and return_pct > -0.10
        notes.append("A neutral view is validated when the security avoids severe downside.")
        return _evaluation(research_stance, success, notes, outcome, pullback_available, breakout_available)

    if "buy" in normalized or "build" in normalized:
        success = return_pct is not None and return_pct > 0 and outcome.hit_stop is not True
        notes.append("Immediate buy/build actions require positive follow-through without stop breach.")
        return _evaluation(research_stance, success, notes, outcome, pullback_available, breakout_available)

    return _evaluation(
        research_stance,
        None,
        ["Action policy is not specific enough for deterministic outcome evaluation."],
        outcome,
        pullback_available,
        breakout_available,
    )


def _evaluation(
    action_type: str,
    success: Optional[bool],
    notes: list[str],
    outcome: WindowOutcome,
    pullback_available: Optional[bool],
    breakout_available: Optional[bool],
) -> ActionEvaluation:
    return ActionEvaluation(
        action_type=action_type,
        success=success,
        notes=notes,
        stop_was_hit=outcome.hit_stop,
        target_was_hit=outcome.hit_target,
        pullback_entry_was_available=pullback_available,
        breakout_confirmation_was_available=breakout_available,
    )
