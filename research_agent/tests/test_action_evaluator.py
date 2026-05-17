from research_agent.outcomes.action_evaluator import evaluate_action_policy
from research_agent.outcomes.price_outcome import WindowOutcome


def _outcome(
    return_pct=0.03,
    max_gain_pct=0.08,
    max_drawdown_pct=-0.06,
    hit_stop=False,
    hit_target=False,
):
    return WindowOutcome(
        window="60d",
        start_price=100,
        start_date="2026-05-01",
        end_date="2026-07-30",
        end_price=100 * (1 + return_pct),
        return_pct=return_pct,
        max_gain_pct=max_gain_pct,
        max_drawdown_pct=max_drawdown_pct,
        hit_stop=hit_stop,
        hit_target=hit_target,
    )


def test_staged_entry_succeeds_when_pullback_available_without_stop_hit():
    evaluation = evaluate_action_policy(
        {"primary_action": "Staged accumulation"},
        _outcome(max_drawdown_pct=-0.07, hit_stop=False),
    )

    assert evaluation.success
    assert evaluation.pullback_entry_was_available
    assert not evaluation.stop_was_hit


def test_staged_entry_fails_when_stop_is_hit():
    evaluation = evaluate_action_policy(
        {"primary_action": "Staged accumulation"},
        _outcome(max_drawdown_pct=-0.07, hit_stop=True),
    )

    assert not evaluation.success
    assert evaluation.stop_was_hit


def test_trim_succeeds_when_later_drawdown_validates_reduction():
    evaluation = evaluate_action_policy(
        {"primary_action": "Trim partial exposure"},
        _outcome(return_pct=-0.04, max_drawdown_pct=-0.11),
    )

    assert evaluation.success


def test_hold_fails_on_severe_downside():
    evaluation = evaluate_action_policy(
        {"primary_action": "Maintain existing position"},
        _outcome(return_pct=-0.14, max_drawdown_pct=-0.18),
    )

    assert not evaluation.success


def test_target_and_breakout_flags_are_preserved():
    evaluation = evaluate_action_policy(
        {"primary_action": "Build position"},
        _outcome(return_pct=0.10, max_gain_pct=0.12, hit_target=True),
    )

    assert evaluation.success
    assert evaluation.target_was_hit
    assert evaluation.breakout_confirmation_was_available
