from research_agent.outcomes.benchmark_outcome import calculate_benchmark_outcome
from research_agent.outcomes.price_outcome import WindowOutcome
from research_agent.outcomes.rating_evaluator import evaluate_rating_success


def _outcome(return_pct, max_drawdown_pct=-0.04):
    return WindowOutcome(
        window="60d",
        start_price=100,
        start_date="2026-05-01",
        end_date="2026-07-30",
        end_price=100 * (1 + return_pct),
        return_pct=return_pct,
        max_gain_pct=max(return_pct, 0),
        max_drawdown_pct=max_drawdown_pct,
    )


def test_buy_success_requires_positive_absolute_and_relative_return():
    benchmark = calculate_benchmark_outcome("QQQ", stock_return_pct=0.12, benchmark_return_pct=0.05)

    assert evaluate_rating_success("Buy", _outcome(0.03), _outcome(0.12), benchmark)


def test_buy_fails_when_benchmark_relative_return_is_negative():
    benchmark = calculate_benchmark_outcome("QQQ", stock_return_pct=0.03, benchmark_return_pct=0.08)

    assert not evaluate_rating_success("Buy", _outcome(0.01), _outcome(0.03), benchmark)


def test_hold_succeeds_when_severe_underperformance_is_avoided():
    assert evaluate_rating_success("Hold", _outcome(-0.02), _outcome(-0.09))
    assert not evaluate_rating_success("Hold", _outcome(-0.02), _outcome(-0.12))


def test_tactical_trim_succeeds_on_negative_or_relative_weakness():
    benchmark = calculate_benchmark_outcome("QQQ", stock_return_pct=0.01, benchmark_return_pct=0.07)

    assert evaluate_rating_success("Tactical Trim", _outcome(-0.01), _outcome(-0.04))
    assert evaluate_rating_success("Tactical Trim", _outcome(0.01), _outcome(0.01), benchmark)


def test_accumulate_tolerates_pullback_without_large_drawdown():
    assert evaluate_rating_success("Accumulate", _outcome(0.02), _outcome(0.02, max_drawdown_pct=-0.10))
    assert not evaluate_rating_success("Accumulate", _outcome(-0.02), _outcome(-0.02, max_drawdown_pct=-0.20))
