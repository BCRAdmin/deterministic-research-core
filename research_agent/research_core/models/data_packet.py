from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class PriceBasis(BaseModel):
    close: float
    date: str
    currency: str = "USD"
    source: str
    series_adjustment_status: str = "unknown"
    corporate_action_count: int = 0


class FiscalContext(BaseModel):
    latest_fiscal_year: Optional[str] = None
    latest_quarter: Optional[str] = None
    fiscal_year_end: Optional[str] = None


class EventInfo(BaseModel):
    next_earnings_date: Optional[str] = None
    confirmed: bool = False
    source: Optional[str] = None
    status: str = "unavailable"


class OperatingKpiEvidence(BaseModel):
    metric_name: str
    value: float
    raw_value: Optional[float] = None
    unit: str
    source_scale: Optional[str] = None
    source_unit: Optional[str] = None
    source_sign: Optional[Literal[-1, 1]] = None
    currency: Optional[str] = None
    column_label: Optional[str] = None
    dimension: Optional[str] = None
    display_unit: Optional[str] = None
    period_kind: Optional[str] = None
    presentation_basis: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    current_period_start: Optional[str] = None
    current_period_end: Optional[str] = None
    comparison_period_start: Optional[str] = None
    comparison_period_end: Optional[str] = None
    metric_role: Optional[str] = None
    mapping_status: str = "mapped"


class MaterialNewsEvent(BaseModel):
    date: str
    headline: str
    event_type: str
    source_id: str
    source_type: str
    url: Optional[str] = None
    summary: Optional[str] = None
    filing_items: List[str] = Field(default_factory=list)
    content_complete: Optional[bool] = None
    dependency_status: Optional[str] = None
    report_disposition: Optional[str] = None
    report_disposition_reason: Optional[str] = None
    superseded_by: Optional[str] = None
    materiality_rationale: Optional[str] = None
    inventory_filter_reason: Optional[str] = None
    semantic_disposition: Optional[str] = None
    legal_context: Optional[dict] = None
    numeric_evidence: List[OperatingKpiEvidence] = Field(default_factory=list)


class NewsCoverage(BaseModel):
    status: str = "unavailable"
    checked_at: Optional[str] = None
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    sources_checked: List[str] = Field(default_factory=list)
    material_events: List[MaterialNewsEvent] = Field(default_factory=list)


class ForwardEPS(BaseModel):
    value: Optional[float] = None
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    period: Optional[str] = None
    basis: Optional[str] = None
    confirmed_by_company: bool = False


class CompanyGuidanceEPS(BaseModel):
    low: Optional[float] = None
    high: Optional[float] = None
    source_type: str = "company_ir"
    period: Optional[str] = None
    basis: Optional[str] = None


class CompanyGuidanceMetric(BaseModel):
    metric_name: str
    low: float
    high: float
    unit: str
    period: str
    basis: str = "company_defined"
    direction: str = "updated"
    lower_bound: str = "inclusive"
    upper_bound: str = "inclusive"
    source_id: str
    source_type: str
    url: Optional[str] = None


class DataPacket(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    cik: Optional[str] = None
    exchange: Optional[str] = None
    exchange_display_name: Optional[str] = None
    jurisdiction: Optional[str] = None
    incorporation_state: Optional[str] = None
    isin: Optional[str] = None
    wkn: Optional[str] = None
    as_of_date: str
    price_basis: PriceBasis
    fiscal_context: FiscalContext = Field(default_factory=FiscalContext)
    next_events: EventInfo = Field(default_factory=EventInfo)
    news_coverage: NewsCoverage = Field(default_factory=NewsCoverage)
    source_registry_id: str
    forward_eps: Optional[ForwardEPS] = None
    company_guidance_eps: Optional[CompanyGuidanceEPS] = None
    company_guidance: List[CompanyGuidanceMetric] = Field(default_factory=list)
