from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from research_agent.calibration.strategy_quality import (
    DailyStrategyReturn,
    StrategyDefinition,
    assess_strategy_metrics,
)


HASH = "sha256:" + "b" * 64


def _definition() -> StrategyDefinition:
    return StrategyDefinition(
        strategy_id="room16_equal_weight_rating_v1",
        version="1.0.0",
        portfolio_construction="Equal-weight at rebalance with maximum 20 positions.",
        signal_to_position_rule="Only human-approved Accumulate ratings enter at rebalance.",
        rebalance_rule="Monthly close-to-close rebalance.",
        benchmark="TOTAL_RETURN_BENCHMARK",
        maximum_positions=20,
        transaction_cost_bps=10,
        annual_risk_free_rate=0.02,
        risk_free_rate_source="Hash-bound official annual risk-free assumption.",
        risk_free_rate_source_sha256=HASH,
        methodology_evidence_sha256=HASH,
    )


def _observations(count: int = 252) -> list[DailyStrategyReturn]:
    start = date(2025, 1, 2)
    return [
        DailyStrategyReturn(
            date=(start + timedelta(days=index)).isoformat(),
            portfolio_return=0.001 if index % 5 else -0.002,
            benchmark_return=0.0005 if index % 6 else -0.001,
        )
        for index in range(count)
    ]


def test_sharpe_is_blocked_without_portfolio_strategy_and_252_observations() -> None:
    review = assess_strategy_metrics(None, [], return_series_sha256=None)
    assert review.status == "not_ready"
    assert "portfolio_strategy_definition_missing" in review.blockers
    assert "strategy_minimum_trading_observations_not_met" in review.blockers
    assert review.sharpe_ratio is None
    assert review.single_report_metric_use_allowed is False
    assert review.automatic_rating_use_allowed is False


def test_strategy_metrics_are_review_evidence_not_a_single_report_signal() -> None:
    review = assess_strategy_metrics(
        _definition(),
        _observations(),
        return_series_sha256=HASH,
    )
    assert review.status == "human_review_required"
    assert review.blockers == []
    assert review.observation_count == 252
    assert review.sharpe_ratio is not None
    assert review.maximum_drawdown is not None
    assert review.single_report_metric_use_allowed is False
    assert review.automatic_rating_use_allowed is False
    assert review.live_activation_allowed is False


def test_strategy_metrics_reject_duplicate_dates_and_impossible_returns() -> None:
    observations = _observations()
    observations[1] = observations[0]
    observations[2] = observations[2].model_copy(update={"portfolio_return": -1.0})

    review = assess_strategy_metrics(
        _definition(),
        observations,
        return_series_sha256=HASH,
    )
    assert review.status == "not_ready"
    assert "strategy_return_date_duplicate_or_noncanonical" in review.blockers
    assert "strategy_return_value_invalid" in review.blockers


def test_strategy_definition_rejects_impossible_risk_free_rate() -> None:
    with pytest.raises(ValidationError):
        StrategyDefinition.model_validate(
            _definition().model_dump() | {"annual_risk_free_rate": -1.0}
        )
