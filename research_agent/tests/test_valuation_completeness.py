import pytest

from research_agent.research_core.calculations.valuation import (
    calculate_valuation_metrics,
)
from research_agent.research_core.models.metrics_packet import (
    MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED,
    FundamentalMetrics,
)


def _fundamentals(**updates):
    payload = {
        "fiscal_period": "TTM",
        "revenue_ttm": 25_000_000_000,
        "operating_income_ttm": 11_000_000_000,
        "net_income_ttm": 8_400_000_000,
        "free_cash_flow_ttm": 7_200_000_000,
        "cash_and_equivalents": 1_000_000_000,
        "diluted_share_count": 713_500_000,
        "listed_share_count": 713_500_000,
        "trailing_eps": 8_400_000_000 / 713_500_000,
    }
    payload.update(updates)
    return FundamentalMetrics(**payload)


def test_market_multiples_survive_but_ev_stays_unavailable_without_debt():
    valuation = calculate_valuation_metrics(
        264.76,
        _fundamentals(total_debt=None),
    )

    assert round(valuation.market_cap) == 188_906_260_000
    assert valuation.price_to_fcf is not None
    assert valuation.trailing_pe is not None
    assert valuation.enterprise_value is None
    assert valuation.ev_to_sales is None
    assert valuation.ev_to_ebit is None


def test_ev_is_calculated_only_with_debt_and_cash_present():
    complete = calculate_valuation_metrics(
        264.76,
        _fundamentals(total_debt=40_000_000_000),
    )
    missing_cash = calculate_valuation_metrics(
        264.76,
        _fundamentals(
            total_debt=40_000_000_000,
            cash_and_equivalents=None,
        ),
    )

    assert complete.enterprise_value == 227_906_260_000
    assert missing_cash.enterprise_value is None


def test_market_cap_does_not_use_period_average_diluted_shares():
    valuation = calculate_valuation_metrics(
        264.76,
        _fundamentals(listed_share_count=None),
    )

    assert valuation.market_cap is None
    assert valuation.market_cap_share_basis is None
    assert valuation.enterprise_value is None
    assert valuation.ev_to_sales is None
    assert valuation.price_to_fcf is None
    assert valuation.fcf_yield is None
    assert valuation.trailing_pe is not None


def test_market_cap_rejects_unverified_multi_class_price_equivalence():
    valuation = calculate_valuation_metrics(
        264.76,
        _fundamentals(
            listed_share_count=None,
            economic_share_count=1_200_000_000,
            economic_share_count_basis=(
                MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED
            ),
        ),
    )

    assert valuation.market_cap is None
    assert valuation.market_cap_share_basis is None
    assert valuation.enterprise_value is None
    assert valuation.ev_to_sales is None
    assert valuation.price_to_fcf is None
    assert valuation.trailing_pe is not None
    assert valuation.scenario_market_cap == 317_712_000_000
    assert valuation.scenario_price_to_fcf == pytest.approx(44.126666666666665)
    assert valuation.scenario_fcf_yield == pytest.approx(0.02266203353980964)
    assert valuation.scenario_share_basis == "economic_share_count_at_listed_class_price"
    assert "illustrative" in valuation.scenario_limitation.lower()
