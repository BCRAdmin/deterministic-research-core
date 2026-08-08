from __future__ import annotations

from typing import Optional

from research_agent.research_core.models.data_packet import CompanyGuidanceEPS, ForwardEPS
from research_agent.research_core.models.metrics_packet import (
    MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED,
    FundamentalMetrics,
    ValuationMetrics,
    ValuationScenario,
    ValuationSensitivity,
)


DCF_FORECAST_YEARS = 5
DCF_BASE_DISCOUNT_RATE = 0.10
DCF_BASE_TERMINAL_GROWTH_RATE = 0.02


def market_cap(close_price: float, diluted_shares: float):
    return close_price * diluted_shares


def enterprise_value(
    market_cap: float,
    total_debt: float,
    cash_and_equivalents: float,
    short_term_investments: float = 0.0,
    marketable_securities: float = 0.0,
    preferred_equity: float = 0.0,
    minority_interest: float = 0.0,
):
    liquid_assets = cash_and_equivalents + short_term_investments + marketable_securities
    return market_cap + total_debt + preferred_equity + minority_interest - liquid_assets


def price_to_fcf(market_cap: float, fcf_ttm: float):
    if fcf_ttm <= 0:
        return None
    return market_cap / fcf_ttm


def pe_ratio(price: float, eps: Optional[float]):
    if eps is None or eps <= 0:
        return None
    return price / eps


def ev_to_sales(ev: float, revenue_ttm: float):
    if revenue_ttm <= 0:
        return None
    return ev / revenue_ttm


def positive_multiple(numerator: float, denominator: Optional[float]):
    if denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def equity_dcf_value(
    starting_free_cash_flow: float,
    free_cash_flow_growth_rate: float,
    discount_rate: float,
    terminal_growth_rate: float,
    forecast_years: int = DCF_FORECAST_YEARS,
) -> tuple[float, float, float]:
    """Return explicit-period PV, terminal-value PV and total equity value.

    Room16 uses CFO minus CapEx as an equity cash-flow proxy. The function is
    therefore an equity DCF sensitivity, not an FCFF enterprise valuation.
    """

    if starting_free_cash_flow <= 0:
        raise ValueError("starting_free_cash_flow must be positive")
    if forecast_years < 1:
        raise ValueError("forecast_years must be positive")
    if discount_rate <= terminal_growth_rate:
        raise ValueError("discount_rate must exceed terminal_growth_rate")
    if free_cash_flow_growth_rate <= -1:
        raise ValueError("free_cash_flow_growth_rate must be greater than -100%")

    explicit_pv = 0.0
    cash_flow = starting_free_cash_flow
    for year in range(1, forecast_years + 1):
        cash_flow *= 1 + free_cash_flow_growth_rate
        explicit_pv += cash_flow / ((1 + discount_rate) ** year)
    terminal_value = (
        cash_flow
        * (1 + terminal_growth_rate)
        / (discount_rate - terminal_growth_rate)
    )
    terminal_pv = terminal_value / ((1 + discount_rate) ** forecast_years)
    return explicit_pv, terminal_pv, explicit_pv + terminal_pv


def calculate_valuation_sensitivity(
    *,
    close_price: float,
    fundamentals: FundamentalMetrics,
    current_market_cap: Optional[float],
    market_cap_share_basis: Optional[str],
    illustrative_market_cap: Optional[float] = None,
) -> ValuationSensitivity:
    fcf = fundamentals.free_cash_flow_ttm
    if fcf is None or fcf <= 0:
        return ValuationSensitivity(
            limitations=[
                "A positive TTM free-cash-flow anchor is required for the standardized equity DCF sensitivity."
            ]
        )

    observed_growth = fundamentals.revenue_growth_yoy
    anchor_growth = _clamp(observed_growth if observed_growth is not None else 0.05, -0.05, 0.15)
    anchor_basis = (
        "reported_revenue_growth_yoy_capped_for_sensitivity"
        if observed_growth is not None
        else "policy_default_due_to_missing_revenue_growth"
    )
    share_count = _share_count_for_basis(fundamentals, market_cap_share_basis)
    scenario_specs = (
        ("bear", _clamp(anchor_growth - 0.10, -0.15, 0.15), 0.12, 0.01),
        ("base", anchor_growth, DCF_BASE_DISCOUNT_RATE, DCF_BASE_TERMINAL_GROWTH_RATE),
        ("bull", _clamp(anchor_growth + 0.10, 0.0, 0.25), 0.08, 0.03),
    )
    scenarios: list[ValuationScenario] = []
    for name, growth, discount, terminal_growth in scenario_specs:
        explicit_pv, terminal_pv, equity_value = equity_dcf_value(
            starting_free_cash_flow=float(fcf),
            free_cash_flow_growth_rate=growth,
            discount_rate=discount,
            terminal_growth_rate=terminal_growth,
        )
        implied_price = equity_value / share_count if share_count else None
        scenarios.append(
            ValuationScenario(
                name=name,
                starting_free_cash_flow=float(fcf),
                free_cash_flow_growth_rate=growth,
                discount_rate=discount,
                terminal_growth_rate=terminal_growth,
                present_value_explicit_cash_flows=explicit_pv,
                present_value_terminal_value=terminal_pv,
                equity_value=equity_value,
                implied_price=implied_price,
                upside_to_current_price=(implied_price / close_price - 1)
                if implied_price is not None and close_price > 0
                else None,
            )
        )

    target_market_cap = current_market_cap
    reverse_status = "measured"
    status = "measured"
    limitations = [
        "Scenario growth, discount and terminal-growth rates are standardized sensitivity assumptions, not company guidance or a point forecast.",
        "Revenue growth is used only as a capped scenario anchor; durable FCF growth still requires reinvestment and human business-model review.",
        "The model does not replace relative valuation, segment analysis or a human assessment of competitive durability.",
        "The operating-company cash-flow policy is not a sector model for banks, insurers or other regulated financial institutions; those require a dedicated adapter before publication.",
    ]
    if target_market_cap is None:
        target_market_cap = illustrative_market_cap
        reverse_status = "illustrative_unverified_share_equivalence" if target_market_cap else "not_measured"
        status = "illustrative_only"
        limitations.append(
            "Current equity value is illustrative because point-in-time cross-class price equivalence is not independently verified."
        )
    implied_growth = (
        _solve_implied_growth(
            starting_free_cash_flow=float(fcf),
            target_equity_value=float(target_market_cap),
            discount_rate=DCF_BASE_DISCOUNT_RATE,
            terminal_growth_rate=DCF_BASE_TERMINAL_GROWTH_RATE,
        )
        if target_market_cap is not None
        else None
    )
    if target_market_cap is not None and implied_growth is None:
        reverse_status = "outside_solver_range"

    model_values = [scenario.equity_value for scenario in scenarios]
    return ValuationSensitivity(
        status=status,
        anchor_growth_rate=anchor_growth,
        anchor_growth_basis=anchor_basis,
        current_market_cap=current_market_cap,
        current_price=close_price,
        share_basis=market_cap_share_basis,
        reverse_dcf_implied_fcf_growth=implied_growth,
        reverse_dcf_status=reverse_status,
        model_range_low=min(model_values),
        model_range_base=scenarios[1].equity_value,
        model_range_high=max(model_values),
        current_value_position=_current_value_position(
            target_market_cap,
            min(model_values),
            scenarios[1].equity_value,
            max(model_values),
        ),
        scenarios=scenarios,
        limitations=limitations,
    )


def calculate_valuation_metrics(
    close_price: float,
    fundamentals: FundamentalMetrics,
    forward_eps: Optional[ForwardEPS] = None,
    company_guidance_eps: Optional[CompanyGuidanceEPS] = None,
    trailing_eps: Optional[float] = None,
    growth_rate: Optional[float] = None,
) -> ValuationMetrics:
    market_value = None
    ev = None
    economic_share_count_eligible = (
        fundamentals.economic_share_count_basis
        != MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED
    )
    share_count = fundamentals.listed_share_count or (
        fundamentals.economic_share_count
        if economic_share_count_eligible
        else None
    )
    share_basis = None
    if fundamentals.listed_share_count is not None:
        share_basis = "listed_share_count"
    elif (
        fundamentals.economic_share_count is not None
        and economic_share_count_eligible
    ):
        share_basis = "economic_share_count"
    if share_count is not None:
        market_value = market_cap(close_price, share_count)
    if (
        market_value is not None
        and fundamentals.total_debt is not None
        and fundamentals.cash_and_equivalents is not None
    ):
        ev = enterprise_value(
            market_cap=market_value,
            total_debt=fundamentals.total_debt,
            cash_and_equivalents=fundamentals.cash_and_equivalents,
            short_term_investments=fundamentals.short_term_investments or 0.0,
            marketable_securities=fundamentals.marketable_securities or 0.0,
        )

    guidance_midpoint = None
    if (
        company_guidance_eps is not None
        and company_guidance_eps.low is not None
        and company_guidance_eps.high is not None
    ):
        guidance_midpoint = (company_guidance_eps.low + company_guidance_eps.high) / 2

    forward_pe_consensus = pe_ratio(close_price, forward_eps.value) if forward_eps else None
    forward_pe_guidance = pe_ratio(close_price, guidance_midpoint)
    trailing_pe = pe_ratio(close_price, trailing_eps or fundamentals.trailing_eps)
    scenario_market_value = None
    scenario_price_fcf = None
    scenario_fcf_return = None
    scenario_share_basis = None
    scenario_limitation = None
    if (
        fundamentals.economic_share_count is not None
        and not economic_share_count_eligible
    ):
        scenario_market_value = market_cap(
            close_price,
            fundamentals.economic_share_count,
        )
        if fundamentals.free_cash_flow_ttm is not None:
            scenario_price_fcf = price_to_fcf(
                scenario_market_value,
                fundamentals.free_cash_flow_ttm,
            )
            if scenario_market_value:
                scenario_fcf_return = (
                    fundamentals.free_cash_flow_ttm / scenario_market_value
                )
        scenario_share_basis = "economic_share_count_at_listed_class_price"
        scenario_limitation = (
            "Illustrative scenario only: applies the listed-class close to all "
            "filed economic shares although cross-class market-price equivalence "
            "is not independently observable."
        )

    valuation = ValuationMetrics(
        market_cap=market_value,
        enterprise_value=ev,
        price_to_fcf=price_to_fcf(market_value, fundamentals.free_cash_flow_ttm)
        if market_value is not None and fundamentals.free_cash_flow_ttm is not None
        else None,
        fcf_yield=(fundamentals.free_cash_flow_ttm / market_value)
        if market_value and fundamentals.free_cash_flow_ttm is not None
        else None,
        ev_to_sales=ev_to_sales(ev, fundamentals.revenue_ttm)
        if ev is not None and fundamentals.revenue_ttm is not None
        else None,
        ev_to_ebit=positive_multiple(ev, fundamentals.operating_income_ttm)
        if ev is not None
        else None,
        ev_to_ebitda=positive_multiple(ev, fundamentals.ebitda_ttm) if ev is not None else None,
        trailing_pe=trailing_pe,
        forward_pe_consensus=forward_pe_consensus,
        forward_pe_guidance=forward_pe_guidance,
        peg_ratio=(forward_pe_consensus / growth_rate)
        if forward_pe_consensus is not None and growth_rate not in (None, 0)
        else None,
        market_cap_share_basis=share_basis,
        scenario_market_cap=scenario_market_value,
        scenario_price_to_fcf=scenario_price_fcf,
        scenario_fcf_yield=scenario_fcf_return,
        scenario_share_basis=scenario_share_basis,
        scenario_limitation=scenario_limitation,
    )
    valuation.sensitivity = calculate_valuation_sensitivity(
        close_price=close_price,
        fundamentals=fundamentals,
        current_market_cap=market_value,
        market_cap_share_basis=share_basis,
        illustrative_market_cap=scenario_market_value,
    )
    return valuation


def _share_count_for_basis(
    fundamentals: FundamentalMetrics,
    share_basis: Optional[str],
) -> Optional[float]:
    if share_basis == "listed_share_count":
        return fundamentals.listed_share_count
    if share_basis == "economic_share_count":
        return fundamentals.economic_share_count
    return None


def _solve_implied_growth(
    *,
    starting_free_cash_flow: float,
    target_equity_value: float,
    discount_rate: float,
    terminal_growth_rate: float,
) -> Optional[float]:
    if starting_free_cash_flow <= 0 or target_equity_value <= 0:
        return None
    low, high = -0.50, 1.00
    low_value = equity_dcf_value(
        starting_free_cash_flow,
        low,
        discount_rate,
        terminal_growth_rate,
    )[2]
    high_value = equity_dcf_value(
        starting_free_cash_flow,
        high,
        discount_rate,
        terminal_growth_rate,
    )[2]
    if not low_value <= target_equity_value <= high_value:
        return None
    for _ in range(100):
        midpoint = (low + high) / 2
        midpoint_value = equity_dcf_value(
            starting_free_cash_flow,
            midpoint,
            discount_rate,
            terminal_growth_rate,
        )[2]
        if midpoint_value < target_equity_value:
            low = midpoint
        else:
            high = midpoint
    return (low + high) / 2


def _current_value_position(
    current_value: Optional[float],
    low: float,
    base: float,
    high: float,
) -> str:
    if current_value is None:
        return "not_measured"
    if current_value < low:
        return "below_model_range"
    if current_value > high:
        return "above_model_range"
    if current_value < base:
        return "within_lower_model_range"
    return "within_upper_model_range"


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
