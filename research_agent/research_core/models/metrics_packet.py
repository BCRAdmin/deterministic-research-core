from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


MULTI_CLASS_PRICE_EQUIVALENCE_UNVERIFIED = (
    "multi_class_unverified_price_equivalence"
)


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
    cash_and_short_term_investments: Optional[float] = None
    liquidity_basis: Optional[str] = None
    balance_sheet_metric_statuses: Dict[str, str] = Field(default_factory=dict)
    total_debt: Optional[float] = None
    short_term_debt: Optional[float] = None
    debt_current: Optional[float] = None
    debt_noncurrent: Optional[float] = None
    credit_facility_borrowings: Optional[float] = None
    lease_liability_current: Optional[float] = None
    lease_liability_noncurrent: Optional[float] = None
    total_lease_liabilities: Optional[float] = None
    current_assets: Optional[float] = None
    current_liabilities: Optional[float] = None
    equity: Optional[float] = None
    net_cash: Optional[float] = None
    net_cash_basis: Optional[str] = None
    current_ratio: Optional[float] = None
    debt_to_equity: Optional[float] = None
    deferred_revenue: Optional[float] = None
    diluted_share_count: Optional[float] = None
    listed_share_count: Optional[float] = None
    treasury_share_count: Optional[float] = None
    treasury_stock_value: Optional[float] = None
    economic_share_count: Optional[float] = None
    economic_share_count_basis: Optional[str] = None
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
    scenario_market_cap: Optional[float] = None
    scenario_price_to_fcf: Optional[float] = None
    scenario_fcf_yield: Optional[float] = None
    scenario_share_basis: Optional[str] = None
    scenario_limitation: Optional[str] = None
    sensitivity: "ValuationSensitivity" = Field(
        default_factory=lambda: ValuationSensitivity()
    )


class ValuationScenario(BaseModel):
    name: Literal["bear", "base", "bull"]
    forecast_years: int = 5
    starting_free_cash_flow: float
    free_cash_flow_growth_rate: float
    discount_rate: float
    terminal_growth_rate: float
    present_value_explicit_cash_flows: float
    present_value_terminal_value: float
    terminal_value_share: float
    equity_value: float
    implied_price: Optional[float] = None
    upside_to_current_price: Optional[float] = None
    assumption_basis: str = "standardized_sensitivity_not_forecast"


class ValuationSensitivity(BaseModel):
    method_id: str = "equity_dcf_sensitivity_v1"
    policy_version: str = "room16_analytical_core_v0_2"
    status: Literal["measured", "illustrative_only", "not_measured"] = (
        "not_measured"
    )
    anchor_growth_rate: Optional[float] = None
    anchor_growth_basis: Optional[str] = None
    current_market_cap: Optional[float] = None
    current_price: Optional[float] = None
    share_basis: Optional[str] = None
    reverse_dcf_implied_fcf_growth: Optional[float] = None
    reverse_dcf_status: str = "not_measured"
    model_range_low: Optional[float] = None
    model_range_base: Optional[float] = None
    model_range_high: Optional[float] = None
    current_value_position: str = "not_measured"
    scenarios: List[ValuationScenario] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class RiskComponent(BaseModel):
    component_id: str
    label: str
    weight: float
    status: Literal["measured", "partial", "not_measured"]
    score: Optional[float] = None
    coverage_ratio: float = 0.0
    effective_weight: float = 0.0
    observations: List[str] = Field(default_factory=list)
    missing_inputs: List[str] = Field(default_factory=list)


class IssuerRiskAssessment(BaseModel):
    method_id: str = "issuer_financial_risk_v1"
    policy_version: str = "room16_analytical_core_v0_2"
    status: Literal["partial", "not_measured"] = "not_measured"
    financial_risk_score: Optional[float] = None
    financial_risk_band: str = "not_measured"
    measured_weight: float = 0.0
    total_weight: float = 1.0
    coverage_ratio: float = 0.0
    components: List[RiskComponent] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    disclosed_business_risk_categories: List[str] = Field(default_factory=list)
    qualitative_business_risk_status: str = "human_review_required"
    limitations: List[str] = Field(default_factory=list)


class MetricsPacket(BaseModel):
    ticker: str
    as_of_date: str
    technical: TechnicalMetrics
    fundamentals: FundamentalMetrics
    valuation: ValuationMetrics
    risk: IssuerRiskAssessment = Field(default_factory=IssuerRiskAssessment)
