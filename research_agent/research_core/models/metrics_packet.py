from typing import Dict, Optional

from pydantic import BaseModel, Field


class TechnicalMetrics(BaseModel):
    indicator_date: str
    close: float
    sma_10: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_10: Optional[float] = None
    ema_20: Optional[float] = None
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_mid: Optional[float] = None
    bollinger_lower: Optional[float] = None
    atr_14: Optional[float] = None
    avg_volume_20: Optional[float] = None
    price_series_basis: str = "unknown"
    corporate_action_count: int = 0
    distance_to_sma_10_pct: Optional[float] = None
    distance_to_sma_20_pct: Optional[float] = None
    distance_to_sma_50_pct: Optional[float] = None
    distance_to_sma_200_pct: Optional[float] = None
    distance_to_ema_10_pct: Optional[float] = None
    distance_to_ema_20_pct: Optional[float] = None
    signals: Dict[str, object] = Field(default_factory=dict)


class FundamentalMetrics(BaseModel):
    fiscal_period: str
    revenue_growth_yoy: Optional[float] = None
    current_period_revenue_growth_yoy: Optional[float] = None
    current_period_operating_income_growth_yoy: Optional[float] = None
    current_period_net_income_growth_yoy: Optional[float] = None
    revenue_ttm: Optional[float] = None
    gross_profit_ttm: Optional[float] = None
    operating_income_ttm: Optional[float] = None
    ebitda_ttm: Optional[float] = None
    net_income_ttm: Optional[float] = None
    operating_cash_flow_ttm: Optional[float] = None
    capex_ttm: Optional[float] = None
    free_cash_flow_ttm: Optional[float] = None
    free_cash_flow_formula: Optional[str] = None
    free_cash_flow_definition_basis: Optional[str] = None
    gross_margin_ttm: Optional[float] = None
    operating_margin_ttm: Optional[float] = None
    net_margin_ttm: Optional[float] = None
    fcf_margin_ttm: Optional[float] = None
    free_cash_flow_conversion_ttm: Optional[float] = None
    sbc_ttm: Optional[float] = None
    sbc_to_revenue: Optional[float] = None
    sbc_to_fcf: Optional[float] = None
    sbc_to_non_gaap_operating_income: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    short_term_investments: Optional[float] = None
    marketable_securities: Optional[float] = None
    cash_and_investments: Optional[float] = None
    total_debt: Optional[float] = None
    short_term_debt: Optional[float] = None
    debt_current: Optional[float] = None
    debt_noncurrent: Optional[float] = None
    lease_liability_current: Optional[float] = None
    lease_liability_noncurrent: Optional[float] = None
    total_lease_liabilities: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    equity: Optional[float] = None
    net_cash: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    deferred_revenue: Optional[float] = None
    diluted_share_count: Optional[float] = None
    listed_share_count: Optional[float] = None
    treasury_share_count: Optional[float] = None
    treasury_stock_value: Optional[float] = None
    economic_share_count: Optional[float] = None
    trailing_eps: Optional[float] = None
    diluted_share_count_yoy: Optional[float] = None
    buybacks: Optional[float] = None
    dividends_paid: Optional[float] = None
    shareholder_distributions_ttm: Optional[float] = None
    shareholder_distributions_minus_fcf_ttm: Optional[float] = None
    depreciation_and_amortization_ttm: Optional[float] = None
    interest_expense_ttm: Optional[float] = None
    operating_income_interest_coverage_ttm: Optional[float] = None
    free_cash_flow_interest_coverage_ttm: Optional[float] = None


class ValuationMetrics(BaseModel):
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    price_to_fcf: Optional[float] = None
    fcf_yield: Optional[float] = None
    ev_to_sales: Optional[float] = None
    ev_to_ebit: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe_consensus: Optional[float] = None
    forward_pe_guidance: Optional[float] = None
    peg_ratio: Optional[float] = None
    market_cap_share_basis: Optional[str] = None


class MetricsPacket(BaseModel):
    ticker: str
    as_of_date: str
    technical: TechnicalMetrics
    fundamentals: FundamentalMetrics
    valuation: ValuationMetrics
