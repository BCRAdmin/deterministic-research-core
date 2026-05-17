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
    primary_action = str(action_policy.get("primary_action", "Manual review required"))
    normalized = primary_action.lower()
    notes: list[str] = []
    max_drawdown = outcome.max_drawdown_pct
    max_gain = outcome.max_gain_pct
    return_pct = outcome.return_pct

    pullback_available = max_drawdown is not None and max_drawdown <= pullback_threshold
    breakout_available = max_gain is not None and max_gain >= abs(pullback_threshold)

    if "staged" in normalized or "accumulation" in normalized:
        success = pullback_available and outcome.hit_stop is not True
        notes.append("Staged accumulation succeeds when a pullback entry appears without immediately breaking the stop.")
        return _evaluation(primary_action, success, notes, outcome, pullback_available, breakout_available)

    if "trim" in normalized or "reduce" in normalized or "below target" in normalized:
        drawdown_confirmed = max_drawdown is not None and max_drawdown <= trim_drawdown_threshold
        weakness_confirmed = return_pct is not None and return_pct < 0
        success = drawdown_confirmed or weakness_confirmed
        notes.append("Trim or underweight action succeeds when later weakness validates risk reduction.")
        return _evaluation(primary_action, success, notes, outcome, pullback_available, breakout_available)

    if "maintain" in normalized or "hold" in normalized:
        success = return_pct is not None and return_pct > -0.10
        notes.append("Hold action succeeds when the position avoids severe downside.")
        return _evaluation(primary_action, success, notes, outcome, pullback_available, breakout_available)

    if "buy" in normalized or "build" in normalized:
        success = return_pct is not None and return_pct > 0 and outcome.hit_stop is not True
        notes.append("Immediate buy/build actions require positive follow-through without stop breach.")
        return _evaluation(primary_action, success, notes, outcome, pullback_available, breakout_available)

    return _evaluation(
        primary_action,
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
