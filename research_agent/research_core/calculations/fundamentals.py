from __future__ import annotations

from typing import Any, Mapping, Optional

from research_agent.research_core.models.metrics_packet import FundamentalMetrics
from research_agent.research_core.models.report_config import FCFDefinitionConfig


def safe_divide(numerator: Optional[float], denominator: Optional[float]):
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def ttm_sum(values: list[float]) -> float:
    if len(values) != 4:
        raise ValueError("TTM requires exactly 4 quarterly values.")
    return sum(values)


def gross_margin(gross_profit: float, revenue: float):
    return safe_divide(gross_profit, revenue)


def operating_margin(operating_income: float, revenue: float):
    return safe_divide(operating_income, revenue)


def net_margin(net_income: float, revenue: float):
    return safe_divide(net_income, revenue)


def free_cash_flow(
    operating_cash_flow: float,
    capex: float,
    finance_lease_principal_payments: float = 0.0,
    company_adjustments: float = 0.0,
):
    """
    Company-adjusted FCF:
    CFO - CapEx - principal payments of finance leases + company adjustments.
    If company definition differs, store formula in metadata.
    """
    return (
        operating_cash_flow
        - abs(capex)
        - abs(finance_lease_principal_payments)
        + company_adjustments
    )


def net_cash(
    cash_and_equivalents: Optional[float],
    short_term_investments: Optional[float],
    marketable_securities: Optional[float],
    total_debt: Optional[float],
):
    if total_debt is None or all(
        value is None
        for value in (cash_and_equivalents, short_term_investments, marketable_securities)
    ):
        return None
    liquid_assets = (
        (cash_and_equivalents or 0)
        + (short_term_investments or 0)
        + (marketable_securities or 0)
    )
    return liquid_assets - (total_debt or 0)


def current_ratio(current_assets: float, current_liabilities: float):
    return safe_divide(current_assets, current_liabilities)


def debt_to_equity(total_debt: float, equity: float):
    return safe_divide(total_debt, equity)


def sbc_ratios(
    sbc: Optional[float],
    revenue: Optional[float],
    fcf: Optional[float],
    non_gaap_operating_income: Optional[float] = None,
):
    return {
        "sbc_to_revenue": safe_divide(sbc, revenue),
        "sbc_to_fcf": safe_divide(sbc, fcf),
        "sbc_to_non_gaap_operating_income": safe_divide(sbc, non_gaap_operating_income),
    }


def calculate_fundamental_metrics(
    fundamentals: Mapping[str, Any],
    fcf_definition: Optional[FCFDefinitionConfig] = None,
) -> FundamentalMetrics:
    fcf_definition = fcf_definition or FCFDefinitionConfig()
    quarterly = fundamentals.get("quarterly", {})
    annual = fundamentals.get("annual", {})
    balance_sheet = fundamentals.get("balance_sheet", {})
    share_data = fundamentals.get("share_data", {})

    revenue_ttm = _ttm_or_annual_if_present(quarterly, annual, "revenue")
    gross_profit_ttm = _ttm_or_annual_if_present(quarterly, annual, "gross_profit")
    operating_income_ttm = _ttm_or_annual_if_present(quarterly, annual, "operating_income")
    ebitda_ttm = _ttm_or_annual_if_present(quarterly, annual, "ebitda")
    net_income_ttm = _ttm_or_annual_if_present(quarterly, annual, "net_income")
    operating_cash_flow_ttm = _ttm_or_annual_if_present(quarterly, annual, "operating_cash_flow")
    capex_ttm = _ttm_or_annual_if_present(quarterly, annual, "capex")
    company_defined_fcf_ttm = _ttm_or_annual_if_present(quarterly, annual, "free_cash_flow")
    adjusted_fcf_ttm = _ttm_or_annual_if_present(quarterly, annual, "adjusted_free_cash_flow")
    sbc_ttm = _ttm_or_annual_if_present(quarterly, annual, "sbc")

    finance_lease_principal_ttm = _ttm_if_present(
        quarterly,
        "finance_lease_principal_payments",
        default=0.0,
    )

    fcf_ttm = None
    if operating_cash_flow_ttm is not None and capex_ttm is not None:
        fcf_ttm = free_cash_flow(
            operating_cash_flow=operating_cash_flow_ttm,
            capex=capex_ttm if fcf_definition.subtract_capex else 0.0,
            finance_lease_principal_payments=(
                finance_lease_principal_ttm
                if fcf_definition.subtract_finance_lease_principal_payments
                else 0.0
            ),
            company_adjustments=fcf_definition.company_adjustments,
        )
    if company_defined_fcf_ttm is not None:
        fcf_ttm = company_defined_fcf_ttm
    elif adjusted_fcf_ttm is not None:
        fcf_ttm = adjusted_fcf_ttm

    cash_and_equivalents = _optional_float(balance_sheet.get("cash_and_equivalents"))
    short_term_investments = _optional_float(balance_sheet.get("short_term_investments"))
    marketable_securities = _optional_float(balance_sheet.get("marketable_securities"))
    total_debt = _optional_float(balance_sheet.get("total_debt"))
    liquid_values = (
        cash_and_equivalents,
        short_term_investments,
        marketable_securities,
    )
    cash_and_investments = (
        None
        if all(value is None for value in liquid_values)
        else sum(value or 0.0 for value in liquid_values)
    )
    current_assets = _optional_float(balance_sheet.get("current_assets"))
    current_liabilities = _optional_float(balance_sheet.get("current_liabilities"))
    equity = _optional_float(balance_sheet.get("equity"))

    diluted_share_count = _optional_float(share_data.get("diluted_share_count"))
    listed_share_count = _optional_float(share_data.get("listed_share_count"))
    treasury_share_count = _optional_float(share_data.get("treasury_share_count"))
    economic_share_count = _optional_float(share_data.get("economic_share_count"))
    if economic_share_count is None and listed_share_count is not None:
        economic_share_count = listed_share_count - (treasury_share_count or 0.0)
    trailing_eps = safe_divide(net_income_ttm, economic_share_count or diluted_share_count)
    prior_diluted_share_count = _optional_float(share_data.get("diluted_share_count_prior_year"))
    diluted_share_count_yoy = _yoy_change(diluted_share_count, prior_diluted_share_count)

    ratios = sbc_ratios(
        sbc=sbc_ttm,
        revenue=revenue_ttm,
        fcf=fcf_ttm,
        non_gaap_operating_income=_optional_float(fundamentals.get("non_gaap_operating_income_ttm")),
    )

    return FundamentalMetrics(
        fiscal_period=str(fundamentals.get("fiscal_period", "unknown")),
        revenue_growth_yoy=_optional_float(fundamentals.get("revenue_growth_yoy")),
        revenue_ttm=revenue_ttm,
        gross_profit_ttm=gross_profit_ttm,
        operating_income_ttm=operating_income_ttm,
        ebitda_ttm=ebitda_ttm,
        net_income_ttm=net_income_ttm,
        operating_cash_flow_ttm=operating_cash_flow_ttm,
        capex_ttm=capex_ttm,
        free_cash_flow_ttm=fcf_ttm,
        free_cash_flow_formula=fcf_definition.formula_id,
        gross_margin_ttm=gross_margin(gross_profit_ttm, revenue_ttm) if gross_profit_ttm is not None and revenue_ttm is not None else None,
        operating_margin_ttm=operating_margin(operating_income_ttm, revenue_ttm) if operating_income_ttm is not None and revenue_ttm is not None else None,
        net_margin_ttm=net_margin(net_income_ttm, revenue_ttm) if net_income_ttm is not None and revenue_ttm is not None else None,
        fcf_margin_ttm=safe_divide(fcf_ttm, revenue_ttm),
        sbc_ttm=sbc_ttm,
        sbc_to_revenue=ratios["sbc_to_revenue"],
        sbc_to_fcf=ratios["sbc_to_fcf"],
        sbc_to_non_gaap_operating_income=ratios["sbc_to_non_gaap_operating_income"],
        cash_and_equivalents=cash_and_equivalents,
        short_term_investments=short_term_investments,
        marketable_securities=marketable_securities,
        cash_and_investments=cash_and_investments,
        total_debt=total_debt,
        current_assets=current_assets,
        current_liabilities=current_liabilities,
        equity=equity,
        net_cash=net_cash(cash_and_equivalents, short_term_investments, marketable_securities, total_debt),
        current_ratio=current_ratio(current_assets, current_liabilities) if current_assets is not None and current_liabilities is not None else None,
        debt_to_equity=debt_to_equity(total_debt, equity) if total_debt is not None and equity is not None else None,
        deferred_revenue=_optional_float(balance_sheet.get("deferred_revenue")),
        diluted_share_count=diluted_share_count,
        listed_share_count=listed_share_count,
        treasury_share_count=treasury_share_count,
        economic_share_count=economic_share_count,
        trailing_eps=trailing_eps,
        diluted_share_count_yoy=diluted_share_count_yoy,
        buybacks=_optional_float(share_data.get("buybacks")),
    )


def _ttm_if_present(
    quarterly: Mapping[str, Any],
    key: str,
    default: Optional[float] = None,
) -> Optional[float]:
    if key not in quarterly or quarterly[key] is None:
        return default
    return ttm_sum([float(value) for value in quarterly[key]])


def _ttm_or_annual_if_present(
    quarterly: Mapping[str, Any],
    annual: Mapping[str, Any],
    key: str,
    default: Optional[float] = None,
) -> Optional[float]:
    values = quarterly.get(key)
    if values is not None and len(values) == 4:
        return ttm_sum([float(value) for value in values])
    if key in annual and annual[key] is not None:
        return float(annual[key])
    return default


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _yoy_change(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    if current is None or prior is None or prior == 0:
        return None
    return (current - prior) / prior
