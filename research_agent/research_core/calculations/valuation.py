from __future__ import annotations

from typing import Optional

from research_agent.research_core.models.data_packet import CompanyGuidanceEPS, ForwardEPS
from research_agent.research_core.models.metrics_packet import FundamentalMetrics, ValuationMetrics


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
    share_count = (
        fundamentals.listed_share_count
        or fundamentals.economic_share_count
    )
    share_basis = None
    if fundamentals.listed_share_count is not None:
        share_basis = "listed_share_count"
    elif fundamentals.economic_share_count is not None:
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

    return ValuationMetrics(
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
    )
