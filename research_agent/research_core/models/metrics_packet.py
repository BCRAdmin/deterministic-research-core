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
    revenue_ttm: Optional[float] = None
    gross_profit_ttm: Optional[float] = None
    operating_income_ttm: Optional[float] = None
    net_income_ttm: Optional[float] = None
    operating_cash_flow_ttm: Optional[float] = None
    capex_ttm: Optional[float] = None
    free_cash_flow_ttm: Optional[float] = None
    free_cash_flow_formula: Optional[str] = None
    gross_margin_ttm: Optional[float] = None
    operating_margin_ttm: Optional[float] = None
    net_margin_ttm: Optional[float] = None
    fcf_margin_ttm: Optional[float] = None
    sbc_ttm: Optional[float] = None
    sbc_to_revenue: Optional[float] = None
    sbc_to_fcf: Optional[float] = None
    sbc_to_non_gaap_operating_income: Optional[float] = None
    cash_and_equivalents: Optional[float] = None
    short_term_investments: Optional[float] = None
    marketable_securities: Optional[float] = None
    cash_and_investments: Optional[float] = None
    total_debt: Optional[float] = None
    net_cash: Optional[float] = None
    current_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    deferred_revenue: Optional[float] = None
    diluted_share_count: Optional[float] = None
    diluted_share_count_yoy: Optional[float] = None
    buybacks: Optional[float] = None


class ValuationMetrics(BaseModel):
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    price_to_fcf: Optional[float] = None
    ev_to_sales: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe_consensus: Optional[float] = None
    forward_pe_guidance: Optional[float] = None
    peg_ratio: Optional[float] = None


class MetricsPacket(BaseModel):
    ticker: str
    as_of_date: str
    technical: TechnicalMetrics
    fundamentals: FundamentalMetrics
    valuation: ValuationMetrics
