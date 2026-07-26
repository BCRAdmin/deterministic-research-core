import pytest

from research_agent.research_core.calculations.fundamentals import (
    calculate_fundamental_metrics,
    free_cash_flow,
    net_cash,
    safe_divide,
    sbc_ratios,
    ttm_sum,
)
from research_agent.research_core.models.report_config import FCFDefinitionConfig


def test_ttm_sum_requires_exactly_four_quarters():
    assert ttm_sum([1, 2, 3, 4]) == 10
    with pytest.raises(ValueError):
        ttm_sum([1, 2, 3])


def test_fcf_definition_can_include_finance_lease_principal_payments():
    assert free_cash_flow(100, 25, finance_lease_principal_payments=5) == 70


def test_balance_sheet_and_sbc_ratios_are_deterministic():
    assert safe_divide(10, 0) is None
    assert net_cash(50, 20, 10, 30) == 50
    assert sbc_ratios(10, 100, 25, 40) == {
        "sbc_to_revenue": 0.1,
        "sbc_to_fcf": 0.4,
        "sbc_to_non_gaap_operating_income": 0.25,
    }


def test_missing_balance_sheet_inputs_do_not_become_zero():
    assert net_cash(None, None, None, None) is None
    assert net_cash(50, None, None, None) is None
    metrics = calculate_fundamental_metrics({"quarterly": {}, "balance_sheet": {}})
    assert metrics.cash_and_investments is None
    assert metrics.net_cash is None


def test_calculate_fundamental_metrics_builds_ttm_margins_and_fcf():
    metrics = calculate_fundamental_metrics(
        {
            "fiscal_period": "FY2026",
            "quarterly": {
                "revenue": [100, 110, 120, 130],
                "gross_profit": [70, 77, 84, 91],
                "operating_income": [10, 12, 14, 16],
                "net_income": [5, 6, 7, 8],
                "operating_cash_flow": [20, 21, 22, 23],
                "capex": [2, 2, 3, 3],
                "finance_lease_principal_payments": [1, 1, 1, 1],
                "sbc": [4, 4, 5, 5],
            },
            "balance_sheet": {
                "cash_and_equivalents": 40,
                "short_term_investments": 10,
                "marketable_securities": 5,
                "total_debt": 15,
                "current_assets": 100,
                "current_liabilities": 50,
                "equity": 200,
                "deferred_revenue": 33,
            },
            "share_data": {
                "diluted_share_count": 100,
                "diluted_share_count_prior_year": 95,
                "buybacks": 3,
            },
            "non_gaap_operating_income_ttm": 80,
        },
        FCFDefinitionConfig(),
    )

    assert metrics.revenue_ttm == 460
    assert metrics.free_cash_flow_ttm == 72
    assert metrics.gross_margin_ttm == 322 / 460
    assert metrics.net_cash == 40
    assert metrics.current_ratio == 2
    assert metrics.debt_to_equity == 0.075
    assert metrics.sbc_to_non_gaap_operating_income == 18 / 80
