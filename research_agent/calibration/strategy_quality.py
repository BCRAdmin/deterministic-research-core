from __future__ import annotations

import hashlib
import json
import math
import statistics
from datetime import date
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


CONTRACT_ID = "room16.strategy_metric_review@1"
MIN_TRADING_OBSERVATIONS = 252


class StrategyDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    strategy_id: str
    version: str
    portfolio_construction: str
    signal_to_position_rule: str
    rebalance_rule: str
    benchmark: str
    maximum_positions: int = Field(gt=0)
    transaction_cost_bps: float = Field(ge=0)
    return_series_basis: Literal["portfolio_total_return_net_of_declared_costs"] = (
        "portfolio_total_return_net_of_declared_costs"
    )
    benchmark_series_basis: Literal["total_return_adjusted"] = "total_return_adjusted"
    annual_risk_free_rate: float = Field(gt=-1, le=1)
    risk_free_rate_source: str
    risk_free_rate_source_sha256: str
    methodology_evidence_sha256: str
    single_report_metric_use_allowed: Literal[False] = False
    automatic_rating_use_allowed: Literal[False] = False
    human_methodology_review_required: Literal[True] = True

    @field_validator(
        "strategy_id",
        "version",
        "portfolio_construction",
        "signal_to_position_rule",
        "rebalance_rule",
        "benchmark",
        "risk_free_rate_source",
    )
    @classmethod
    def require_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("strategy definition text is missing")
        return cleaned

    @field_validator("methodology_evidence_sha256", "risk_free_rate_source_sha256")
    @classmethod
    def require_hash(cls, value: str) -> str:
        if not _is_sha256(value):
            raise ValueError("strategy methodology evidence hash is invalid")
        return value


class DailyStrategyReturn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    date: str
    portfolio_return: float
    benchmark_return: float


class StrategyMetricReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    contract_id: Literal["room16.strategy_metric_review@1"] = CONTRACT_ID
    status: Literal["not_ready", "human_review_required"]
    observation_count: int
    annualized_return: Optional[float]
    annualized_volatility: Optional[float]
    sharpe_ratio: Optional[float]
    maximum_drawdown: Optional[float]
    benchmark_annualized_return: Optional[float]
    blockers: list[str]
    single_report_metric_use_allowed: Literal[False] = False
    automatic_rating_use_allowed: Literal[False] = False
    live_activation_allowed: Literal[False] = False
    review_sha256: str


def assess_strategy_metrics(
    definition: Optional[StrategyDefinition],
    observations: list[DailyStrategyReturn],
    *,
    return_series_sha256: Optional[str],
) -> StrategyMetricReview:
    blockers: list[str] = []
    if definition is None:
        blockers.append("portfolio_strategy_definition_missing")
    if not _is_sha256(return_series_sha256):
        blockers.append("strategy_return_series_hash_invalid")
    normalized: list[DailyStrategyReturn] = []
    seen_dates: set[str] = set()
    for observation in observations:
        try:
            normalized_date = date.fromisoformat(observation.date).isoformat()
        except ValueError:
            blockers.append("strategy_return_date_invalid")
            continue
        if normalized_date != observation.date or normalized_date in seen_dates:
            blockers.append("strategy_return_date_duplicate_or_noncanonical")
            continue
        values = (observation.portfolio_return, observation.benchmark_return)
        if not all(math.isfinite(value) and value > -1 for value in values):
            blockers.append("strategy_return_value_invalid")
            continue
        seen_dates.add(normalized_date)
        normalized.append(observation)
    normalized.sort(key=lambda item: item.date)
    if len(normalized) < MIN_TRADING_OBSERVATIONS:
        blockers.append("strategy_minimum_trading_observations_not_met")
    annualized_return = None
    annualized_volatility = None
    sharpe_ratio = None
    maximum_drawdown = None
    benchmark_return = None
    if normalized and definition is not None:
        portfolio = [item.portfolio_return for item in normalized]
        benchmark = [item.benchmark_return for item in normalized]
        annualized_return = _annualized_compound_return(portfolio)
        benchmark_return = _annualized_compound_return(benchmark)
        if len(portfolio) >= 2:
            daily_volatility = statistics.stdev(portfolio)
            annualized_volatility = round(daily_volatility * math.sqrt(252), 12)
            if daily_volatility > 0:
                daily_risk_free = (1 + definition.annual_risk_free_rate) ** (1 / 252) - 1
                sharpe_ratio = round(
                    (statistics.fmean(portfolio) - daily_risk_free)
                    / daily_volatility
                    * math.sqrt(252),
                    12,
                )
            else:
                blockers.append("strategy_zero_return_volatility")
        maximum_drawdown = _return_series_drawdown(portfolio)
    blockers = sorted(set(blockers))
    payload: dict[str, Any] = {
        "contract_id": CONTRACT_ID,
        "status": "not_ready" if blockers else "human_review_required",
        "observation_count": len(normalized),
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe_ratio": sharpe_ratio,
        "maximum_drawdown": maximum_drawdown,
        "benchmark_annualized_return": benchmark_return,
        "blockers": blockers,
        "single_report_metric_use_allowed": False,
        "automatic_rating_use_allowed": False,
        "live_activation_allowed": False,
    }
    payload["review_sha256"] = _payload_sha256(payload)
    return StrategyMetricReview.model_validate(payload)


def _annualized_compound_return(values: list[float]) -> float:
    cumulative = math.prod(1 + value for value in values)
    return round(cumulative ** (252 / len(values)) - 1, 12)


def _return_series_drawdown(values: list[float]) -> float:
    cumulative = 1.0
    peak = 1.0
    maximum_drawdown = 0.0
    for value in values:
        cumulative *= 1 + value
        peak = max(peak, cumulative)
        maximum_drawdown = min(maximum_drawdown, cumulative / peak - 1)
    return round(maximum_drawdown, 12)


def _payload_sha256(payload: dict[str, Any]) -> str:
    normalized = {key: value for key, value in payload.items() if key != "review_sha256"}
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _is_sha256(value: Optional[str]) -> bool:
    normalized = str(value or "").removeprefix("sha256:")
    return len(normalized) == 64 and all(character in "0123456789abcdef" for character in normalized)
