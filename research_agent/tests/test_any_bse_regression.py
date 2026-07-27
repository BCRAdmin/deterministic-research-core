import pandas as pd

from research_agent.research_core.calculations.fundamentals import (
    calculate_fundamental_metrics,
)
from research_agent.research_core.calculations.technicals import (
    calculate_technical_metrics,
)
from research_agent.research_core.calculations.valuation import (
    calculate_valuation_metrics,
)
from research_agent.sources.bse.bse_provider import (
    BseIssuer,
    _back_adjust_dividends,
    _extract_report_metrics,
)


ISSUER = BseIssuer(
    ticker="ANY",
    company_name="ANY Security Printing Company PLC",
    isin="HU0000093257",
    currency="HUF",
    issuer_id="3071",
    security_id="4042",
    profile_url="https://www.bse.hu/pages/company_profile/%24security/ANY",
)


def test_any_dividend_is_back_adjusted_without_rewriting_raw_close():
    prices = pd.DataFrame([
        {"date": "2026-07-03", "open": 7_240, "high": 7_300, "low": 7_200, "close": 7_250, "volume": 1},
        {"date": "2026-07-07", "open": 6_730, "high": 6_800, "low": 6_700, "close": 6_740, "volume": 1},
    ])
    adjusted = _back_adjust_dividends(prices, [{
        "date": "2026-07-06",
        "type": "dividend",
        "amount": 519,
        "description": "519 HUF",
    }])

    assert adjusted.iloc[0]["close"] == 7_250
    assert round(adjusted.iloc[0]["adjusted_close"], 2) == 6_731
    assert adjusted.iloc[1]["adjusted_close"] == 6_740


def test_any_full_report_metrics_unlock_cashflow_balance_sheet_and_valuation():
    annual_text = """
    EBITDA amounted to HUF 14,314 million.
    Net cash provided by operating activities 12,190,577 9,382,641
    Purchase of property, plant and equipment 7 (3,629,101) (3,907,023)
    """
    interim_text = """
    EBITDA is HUF 4,503 million.
    cash and cash equivalents increased and totalled HUF 8,847 million on 31 March 2026.
    Net cash provided by operating activities (3,400,329) 182,149 3,582,478
    Purchase of property, plant and equipment (286,344) (152,940) 133,404
    Total current assets 31,415,162 38,471,201 7,056,039
    Total current liabilities 23,488,997 28,311,650 4,822,653
    Total assets 48,501,745 56,603,253 8,101,508
    Total shareholders' equity 19,984,304 22,842,197 2,857,893
    Short term debt 8,102,012 8,483,299 381,287
    Long term debt 2,711,088 2,913,388 202,300
    Short term part of lease liabilities 435,791 617,510 181,719
    Long term part of lease liabilities 1,223,442 1,441,370 217,928
    Treasury stock 3.03% 0.00% 448,842 3.03% 0.00% 448,842
    TOTAL: 100.00% 100.00% 14,794,650 100.00%
    """
    annual = _extract_report_metrics(
        annual_text,
        ISSUER,
        fiscal_year=2025,
        fiscal_period="FY",
        period_bucket="annual",
        end_date="2025-12-31",
    )
    interim = _extract_report_metrics(
        interim_text,
        ISSUER,
        fiscal_year=2026,
        fiscal_period="Q1",
        period_bucket="quarterly",
        end_date="2026-03-31",
    )
    annual_values = {row["metric_name"]: row["value"] for row in annual}
    values = {row["metric_name"]: row["value"] for row in interim}
    fundamentals = calculate_fundamental_metrics({
        "fiscal_period": "TTM through FY2026_Q1",
        "annual": {
            "revenue": 70_000_000_000,
            "operating_income": 12_000_000_000,
            "net_income": 8_521_000_000,
            "operating_cash_flow": annual_values["operating_cash_flow"],
            "capex": annual_values["capex"],
            "ebitda": 14_314_000_000,
        },
        "balance_sheet": {
            "cash_and_equivalents": values["cash_and_equivalents"],
            "total_debt": values["total_debt"],
            "current_assets": values["current_assets"],
            "current_liabilities": values["current_liabilities"],
            "equity": values["equity"],
        },
        "share_data": {
            "listed_share_count": values["listed_share_count"],
            "treasury_share_count": values["treasury_share_count"],
            "economic_share_count": values["economic_share_count"],
        },
    })
    valuation = calculate_valuation_metrics(6_950, fundamentals)

    assert values["total_debt"] == 13_455_567_000
    assert fundamentals.free_cash_flow_ttm == 8_561_476_000
    assert fundamentals.trailing_eps is not None
    assert valuation.market_cap is not None
    assert valuation.ev_to_ebitda is not None
    assert valuation.market_cap_share_basis == "listed_share_count"


def test_any_bearish_alignment_is_not_falsely_called_death_cross():
    rows = []
    for index in range(240):
        close = 10_000 - index * 12
        rows.append({
            "date": (pd.Timestamp("2025-01-01") + pd.Timedelta(days=index)).date().isoformat(),
            "open": close,
            "high": close + 10,
            "low": close - 10,
            "close": close,
            "adjusted_open": close,
            "adjusted_high": close + 10,
            "adjusted_low": close - 10,
            "adjusted_close": close,
            "volume": 1_000,
        })
    metrics = calculate_technical_metrics(pd.DataFrame(rows))

    assert metrics.signals["ma_50_200_state"] == "bearish_alignment"
    assert metrics.signals["cross_event"] == "none"
    assert metrics.signals["death_cross"] is False
