import pytest

from research_agent.research_core.calculations.fundamentals import (
    calculate_fundamental_metrics,
    debt_to_equity,
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
                "interest_expense": [-1, -1, -1, -1],
                "buybacks": [2, 3, 4, 5],
                "dividends_paid": [6, 7, 8, 9],
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
                "listed_share_count": 98,
                "treasury_share_count": 40,
                "diluted_share_count_prior_year": 95,
                "buybacks": 3,
            },
            "non_gaap_operating_income_ttm": 80,
            "free_cash_flow_definition_basis": "issuer_defined",
            "ttm_bridges": {
                metric: {
                    "period_start": "2025-04-01",
                    "period_end": "2026-03-31",
                }
                for metric in (
                    "operating_cash_flow",
                    "capex",
                    "buybacks",
                    "dividends_paid",
                )
            },
        },
        FCFDefinitionConfig(),
    )

    assert metrics.revenue_ttm == 460
    assert metrics.free_cash_flow_ttm == 76
    assert metrics.free_cash_flow_conversion_ttm == 76 / 26
    assert metrics.free_cash_flow_definition_basis == "issuer_defined"
    assert metrics.interest_expense_ttm == 4
    assert metrics.operating_income_interest_coverage_ttm == 52 / 4
    assert metrics.free_cash_flow_interest_coverage_ttm == 76 / 4
    assert metrics.shareholder_distributions_ttm == 44
    assert metrics.shareholder_distributions_minus_fcf_ttm == -32
    assert metrics.gross_margin_ttm == 322 / 460
    assert metrics.net_cash == 40
    assert metrics.current_ratio == 2
    assert metrics.debt_to_equity == 0.075
    assert metrics.sbc_to_non_gaap_operating_income == 18 / 80
    assert metrics.economic_share_count == 98


def test_shareholder_distributions_require_both_ttm_components():
    metrics = calculate_fundamental_metrics(
        {
            "quarterly": {
                "operating_cash_flow": [20, 20, 20, 20],
                "capex": [5, 5, 5, 5],
                "buybacks": [1, 1, 1, 1],
            },
            "share_data": {"buybacks": 99},
        }
    )

    assert metrics.buybacks == 4
    assert metrics.dividends_paid is None
    assert metrics.shareholder_distributions_ttm is None
    assert metrics.shareholder_distributions_minus_fcf_ttm is None


def test_current_period_shareholder_distributions_use_only_aligned_periods():
    fundamentals = {
        "quarterly": {},
        "current_period": {
            "buybacks": 1_003_000_000,
            "dividends_paid": 764_000_000,
            "operating_cash_flow": 3_227_000_000,
            "capex": 1_280_000_000,
        },
        "current_period_metadata": {
            metric: {
                "period_start": "2026-01-01",
                "period_end": "2026-06-30",
            }
            for metric in (
                "buybacks",
                "dividends_paid",
                "operating_cash_flow",
                "capex",
            )
        },
    }

    metrics = calculate_fundamental_metrics(fundamentals)

    assert metrics.buybacks_current_period == 1_003_000_000
    assert metrics.dividends_paid_current_period == 764_000_000
    assert metrics.shareholder_distributions_current_period == 1_767_000_000
    assert metrics.free_cash_flow_current_period == 1_947_000_000
    assert metrics.shareholder_distributions_minus_fcf_current_period == -180_000_000
    assert metrics.shareholder_distribution_period_start == "2026-01-01"
    assert metrics.shareholder_distribution_period_end == "2026-06-30"
    assert metrics.shareholder_distributions_ttm is None

    fundamentals["current_period_metadata"]["dividends_paid"] = {
        "period_start": "2026-04-01",
        "period_end": "2026-06-30",
    }
    mismatched = calculate_fundamental_metrics(fundamentals)
    assert mismatched.shareholder_distributions_current_period is None
    assert mismatched.shareholder_distributions_minus_fcf_current_period is None


def test_shareholder_distribution_comparison_rejects_mixed_periods():
    shared = {
        "quarterly": {
            "operating_cash_flow": [20, 20, 20, 20],
            "capex": [5, 5, 5, 5],
            "buybacks": [1, 1, 1, 1],
            "dividends_paid": [1, 1, 1, 1],
        },
        "ttm_bridges": {
            metric: {
                "period_start": "2025-04-01",
                "period_end": "2026-03-31",
            }
            for metric in (
                "operating_cash_flow",
                "capex",
                "buybacks",
                "dividends_paid",
            )
        },
    }
    shared["ttm_bridges"]["dividends_paid"] = {
        "period_start": "2025-01-01",
        "period_end": "2025-12-31",
    }

    mixed_distributions = calculate_fundamental_metrics(shared)
    assert mixed_distributions.shareholder_distributions_ttm is None

    shared["ttm_bridges"]["dividends_paid"] = {
        "period_start": "2025-04-01",
        "period_end": "2026-03-31",
    }
    shared["ttm_bridges"]["capex"] = {
        "period_start": "2025-01-01",
        "period_end": "2025-12-31",
    }
    mixed_fcf = calculate_fundamental_metrics(shared)
    assert mixed_fcf.free_cash_flow_ttm is None
    assert mixed_fcf.fcf_margin_ttm is None
    assert mixed_fcf.shareholder_distributions_ttm == 8
    assert mixed_fcf.shareholder_distributions_minus_fcf_ttm is None


def test_free_cash_flow_rejects_mixed_annual_and_trailing_inputs():
    metrics = calculate_fundamental_metrics(
        {
            "quarterly": {},
            "ttm": {"capex": 22_245},
            "annual": {"operating_cash_flow": 40_284},
            "ttm_bridges": {
                "capex": {
                    "period_start": "2025-07-01",
                    "period_end": "2026-06-30",
                }
            },
            "reconciliation_material_dates": {
                "operating_cash_flow": "2025-01-01",
            },
        }
    )

    assert metrics.operating_cash_flow_ttm == 40_284
    assert metrics.capex_ttm == 22_245
    assert metrics.free_cash_flow_ttm is None
    assert metrics.fcf_margin_ttm is None


def test_debt_to_equity_is_not_reported_for_non_positive_equity():
    assert debt_to_equity(40, 0) is None
    assert debt_to_equity(40, -1) is None
