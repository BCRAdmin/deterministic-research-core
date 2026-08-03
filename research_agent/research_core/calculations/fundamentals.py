from __future__ import annotations

from typing import Any, Mapping, Optional

from research_agent.research_core.models.metrics_packet import (
    MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED,
    FundamentalMetrics,
)
from research_agent.research_core.models.report_config import FCFDefinitionConfig


def safe_divide(numerator: Optional[float], denominator: Optional[float]):
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def current_profit_growth_divergence_metrics(
    fundamentals: FundamentalMetrics,
) -> tuple[str, ...]:
    """Return extreme profit comparisons that diverge from current revenue."""

    revenue_growth = fundamentals.current_period_revenue_growth_yoy
    if revenue_growth is None:
        return ()
    return tuple(
        metric_name
        for metric_name, value in (
            (
                "current_period_operating_income_growth_yoy",
                fundamentals.current_period_operating_income_growth_yoy,
            ),
            (
                "current_period_net_income_growth_yoy",
                fundamentals.current_period_net_income_growth_yoy,
            ),
        )
        if value is not None
        and (
            (value >= 0.75 and value - revenue_growth >= 0.75)
            or (value <= -0.50 and revenue_growth - value >= 0.50)
        )
    )


def current_operating_profit_decline_metrics(
    fundamentals: FundamentalMetrics,
) -> tuple[str, ...]:
    """Return measured declines usable as operating-direction evidence.

    Extreme profit/revenue divergences remain reported arithmetic, but are
    excluded from operating-direction language until a causal filing bridge
    explains the base effect or non-recurring item.
    """

    distorted = set(current_profit_growth_divergence_metrics(fundamentals))
    return tuple(
        metric_name
        for metric_name, value in (
            (
                "current_period_operating_income_growth_yoy",
                fundamentals.current_period_operating_income_growth_yoy,
            ),
            (
                "current_period_net_income_growth_yoy",
                fundamentals.current_period_net_income_growth_yoy,
            ),
        )
        if value is not None and value < 0 and metric_name not in distorted
    )


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
    if equity <= 0:
        return None
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
    ttm = fundamentals.get("ttm", {})
    annual = fundamentals.get("annual", {})
    balance_sheet = fundamentals.get("balance_sheet", {})
    share_data = fundamentals.get("share_data", {})

    revenue_ttm = _ttm_or_annual_if_present(quarterly, ttm, annual, "revenue")
    gross_profit_ttm = _ttm_or_annual_if_present(quarterly, ttm, annual, "gross_profit")
    operating_income_ttm = _ttm_or_annual_if_present(quarterly, ttm, annual, "operating_income")
    ebitda_ttm = _ttm_or_annual_if_present(quarterly, ttm, annual, "ebitda")
    net_income_ttm = _ttm_or_annual_if_present(quarterly, ttm, annual, "net_income")
    operating_cash_flow_ttm = _ttm_or_annual_if_present(quarterly, ttm, annual, "operating_cash_flow")
    capex_ttm = _ttm_or_annual_if_present(quarterly, ttm, annual, "capex")
    company_defined_fcf_ttm = _ttm_or_annual_if_present(quarterly, ttm, annual, "free_cash_flow")
    adjusted_fcf_ttm = _ttm_or_annual_if_present(quarterly, ttm, annual, "adjusted_free_cash_flow")
    sbc_ttm = _ttm_or_annual_if_present(quarterly, ttm, annual, "sbc")
    diluted_eps_ttm = _ttm_or_annual_if_present(
        quarterly, ttm, annual, "eps_diluted"
    )
    buybacks_ttm = _ttm_or_annual_if_present(quarterly, ttm, annual, "buybacks")
    dividends_paid_ttm = _ttm_or_annual_if_present(
        quarterly, ttm, annual, "dividends_paid"
    )
    depreciation_and_amortization_ttm = _ttm_or_annual_if_present(
        quarterly, ttm, annual, "depreciation_and_amortization"
    )
    interest_expense_ttm = _ttm_or_annual_if_present(
        quarterly, ttm, annual, "interest_expense"
    )
    if interest_expense_ttm is not None:
        interest_expense_ttm = abs(interest_expense_ttm)
    if (
        ebitda_ttm is None
        and operating_income_ttm is not None
        and depreciation_and_amortization_ttm is not None
    ):
        ebitda_ttm = (
            operating_income_ttm + depreciation_and_amortization_ttm
        )

    finance_lease_principal_ttm = _ttm_if_present(
        quarterly,
        "finance_lease_principal_payments",
        default=0.0,
    )

    fcf_ttm = None
    if (
        operating_cash_flow_ttm is not None
        and capex_ttm is not None
        and _derived_fcf_inputs_are_period_aligned(fundamentals)
    ):
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

    distribution_period = _aligned_ttm_bridge_period(
        fundamentals,
        "buybacks",
        "dividends_paid",
    )
    shareholder_distributions_ttm = (
        buybacks_ttm + dividends_paid_ttm
        if buybacks_ttm is not None
        and dividends_paid_ttm is not None
        and distribution_period is not None
        else None
    )
    fcf_period = _free_cash_flow_ttm_period(
        fundamentals,
        company_defined_fcf_ttm=company_defined_fcf_ttm,
        adjusted_fcf_ttm=adjusted_fcf_ttm,
        operating_cash_flow_ttm=operating_cash_flow_ttm,
        capex_ttm=capex_ttm,
        finance_lease_principal_ttm=finance_lease_principal_ttm,
        fcf_definition=fcf_definition,
    )

    cash_and_equivalents = _optional_float(balance_sheet.get("cash_and_equivalents"))
    short_term_investments = _optional_float(balance_sheet.get("short_term_investments"))
    marketable_securities = _optional_float(balance_sheet.get("marketable_securities"))
    total_debt = _optional_float(balance_sheet.get("total_debt"))
    short_term_debt = _optional_float(balance_sheet.get("short_term_debt"))
    debt_current = _optional_float(balance_sheet.get("debt_current"))
    debt_noncurrent = _optional_float(balance_sheet.get("debt_noncurrent"))
    lease_liability_current = _optional_float(
        balance_sheet.get("lease_liability_current")
    )
    lease_liability_noncurrent = _optional_float(
        balance_sheet.get("lease_liability_noncurrent")
    )
    total_lease_liabilities = _optional_float(
        balance_sheet.get("total_lease_liabilities")
    )
    treasury_stock_value = _optional_float(
        balance_sheet.get("treasury_stock_value")
    )
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
    economic_share_count_basis = (
        str(share_data.get("economic_share_count_basis"))
        if share_data.get("economic_share_count_basis")
        else None
    )
    if economic_share_count is None and listed_share_count is not None:
        # SEC DEI outstanding shares are already net of treasury shares.
        economic_share_count = listed_share_count
        economic_share_count_basis = "listed_share_count"
    trailing_eps = diluted_eps_ttm
    if trailing_eps is None:
        point_in_time_eps_shares = (
            None
            if economic_share_count_basis
            == MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED
            else economic_share_count
        )
        trailing_eps = safe_divide(
            net_income_ttm,
            point_in_time_eps_shares or diluted_share_count,
        )
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
        current_period_revenue_growth_yoy=_optional_float(
            fundamentals.get("current_period_revenue_growth_yoy")
        ),
        current_period_operating_income_growth_yoy=_optional_float(
            fundamentals.get("current_period_operating_income_growth_yoy")
        ),
        current_period_net_income_growth_yoy=_optional_float(
            fundamentals.get("current_period_net_income_growth_yoy")
        ),
        revenue_ttm=revenue_ttm,
        gross_profit_ttm=gross_profit_ttm,
        operating_income_ttm=operating_income_ttm,
        ebitda_ttm=ebitda_ttm,
        net_income_ttm=net_income_ttm,
        operating_cash_flow_ttm=operating_cash_flow_ttm,
        capex_ttm=capex_ttm,
        free_cash_flow_ttm=fcf_ttm,
        free_cash_flow_formula=fcf_definition.formula_id,
        free_cash_flow_definition_basis=(
            str(fundamentals.get("free_cash_flow_definition_basis"))
            if fundamentals.get("free_cash_flow_definition_basis")
            else None
        ),
        gross_margin_ttm=gross_margin(gross_profit_ttm, revenue_ttm) if gross_profit_ttm is not None and revenue_ttm is not None else None,
        operating_margin_ttm=operating_margin(operating_income_ttm, revenue_ttm) if operating_income_ttm is not None and revenue_ttm is not None else None,
        net_margin_ttm=net_margin(net_income_ttm, revenue_ttm) if net_income_ttm is not None and revenue_ttm is not None else None,
        fcf_margin_ttm=safe_divide(fcf_ttm, revenue_ttm),
        free_cash_flow_conversion_ttm=safe_divide(fcf_ttm, net_income_ttm),
        sbc_ttm=sbc_ttm,
        sbc_to_revenue=ratios["sbc_to_revenue"],
        sbc_to_fcf=ratios["sbc_to_fcf"],
        sbc_to_non_gaap_operating_income=ratios["sbc_to_non_gaap_operating_income"],
        cash_and_equivalents=cash_and_equivalents,
        short_term_investments=short_term_investments,
        marketable_securities=marketable_securities,
        cash_and_investments=cash_and_investments,
        total_debt=total_debt,
        short_term_debt=short_term_debt,
        debt_current=debt_current,
        debt_noncurrent=debt_noncurrent,
        lease_liability_current=lease_liability_current,
        lease_liability_noncurrent=lease_liability_noncurrent,
        total_lease_liabilities=total_lease_liabilities,
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
        treasury_stock_value=treasury_stock_value,
        economic_share_count=economic_share_count,
        economic_share_count_basis=economic_share_count_basis,
        trailing_eps=trailing_eps,
        diluted_share_count_yoy=diluted_share_count_yoy,
        buybacks=buybacks_ttm
        if buybacks_ttm is not None
        else _optional_float(share_data.get("buybacks")),
        dividends_paid=dividends_paid_ttm,
        shareholder_distributions_ttm=shareholder_distributions_ttm,
        shareholder_distributions_minus_fcf_ttm=(
            shareholder_distributions_ttm - fcf_ttm
            if shareholder_distributions_ttm is not None
            and fcf_ttm is not None
            and distribution_period == fcf_period
            else None
        ),
        depreciation_and_amortization_ttm=depreciation_and_amortization_ttm,
        interest_expense_ttm=interest_expense_ttm,
        operating_income_interest_coverage_ttm=safe_divide(
            operating_income_ttm,
            interest_expense_ttm,
        ),
        free_cash_flow_interest_coverage_ttm=safe_divide(
            fcf_ttm,
            interest_expense_ttm,
        ),
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
    ttm: Mapping[str, Any],
    annual: Mapping[str, Any],
    key: str,
    default: Optional[float] = None,
) -> Optional[float]:
    values = quarterly.get(key)
    if values is not None and len(values) == 4:
        return ttm_sum([float(value) for value in values])
    if key in ttm and ttm[key] is not None:
        return float(ttm[key])
    if key in annual and annual[key] is not None:
        return float(annual[key])
    return default


def _derived_fcf_inputs_are_period_aligned(
    fundamentals: Mapping[str, Any],
) -> bool:
    """Reject FCF built from cash-flow and capex values on different bases."""

    input_bases = {
        _metric_input_basis(fundamentals, metric_name)
        for metric_name in ("operating_cash_flow", "capex")
    }
    if None in input_bases or len(input_bases) != 1:
        return False

    bridges = fundamentals.get("ttm_bridges")
    if isinstance(bridges, Mapping) and any(
        metric_name in bridges
        for metric_name in ("operating_cash_flow", "capex")
    ):
        return (
            _aligned_ttm_bridge_period(
                fundamentals,
                "operating_cash_flow",
                "capex",
            )
            is not None
        )

    if input_bases == {"annual"}:
        material_dates = fundamentals.get("reconciliation_material_dates")
        if isinstance(material_dates, Mapping):
            dates = [
                str(material_dates.get(metric_name) or "").strip()
                for metric_name in ("operating_cash_flow", "capex")
            ]
            known_dates = [date for date in dates if date]
            if known_dates:
                return len(known_dates) == 2 and len(set(known_dates)) == 1

    return True


def _metric_input_basis(
    fundamentals: Mapping[str, Any],
    key: str,
) -> Optional[str]:
    quarterly = fundamentals.get("quarterly")
    if isinstance(quarterly, Mapping):
        values = quarterly.get(key)
        if values is not None and len(values) == 4:
            return "quarterly"
    ttm = fundamentals.get("ttm")
    if isinstance(ttm, Mapping) and ttm.get(key) is not None:
        return "ttm"
    annual = fundamentals.get("annual")
    if isinstance(annual, Mapping) and annual.get(key) is not None:
        return "annual"
    return None


def _aligned_ttm_bridge_period(
    fundamentals: Mapping[str, Any],
    *metric_names: str,
) -> Optional[tuple[str, str]]:
    bridges = fundamentals.get("ttm_bridges")
    if not isinstance(bridges, Mapping):
        return None
    periods: set[tuple[str, str]] = set()
    for metric_name in metric_names:
        bridge = bridges.get(metric_name)
        if not isinstance(bridge, Mapping):
            return None
        period_start = str(bridge.get("period_start") or "").strip()
        period_end = str(bridge.get("period_end") or "").strip()
        if not period_start or not period_end:
            return None
        periods.add((period_start, period_end))
    return next(iter(periods)) if len(periods) == 1 else None


def _free_cash_flow_ttm_period(
    fundamentals: Mapping[str, Any],
    *,
    company_defined_fcf_ttm: Optional[float],
    adjusted_fcf_ttm: Optional[float],
    operating_cash_flow_ttm: Optional[float],
    capex_ttm: Optional[float],
    finance_lease_principal_ttm: Optional[float],
    fcf_definition: FCFDefinitionConfig,
) -> Optional[tuple[str, str]]:
    if company_defined_fcf_ttm is not None:
        return _aligned_ttm_bridge_period(
            fundamentals,
            "free_cash_flow",
        )
    if adjusted_fcf_ttm is not None:
        return _aligned_ttm_bridge_period(
            fundamentals,
            "adjusted_free_cash_flow",
        )
    if operating_cash_flow_ttm is None or capex_ttm is None:
        return None
    if fcf_definition.company_adjustments:
        return None
    if (
        fcf_definition.subtract_finance_lease_principal_payments
        and finance_lease_principal_ttm
    ):
        return None
    return _aligned_ttm_bridge_period(
        fundamentals,
        "operating_cash_flow",
        "capex",
    )


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _yoy_change(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    if current is None or prior is None or prior == 0:
        return None
    return (current - prior) / prior
