from typing import Optional

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


class DataPacket(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    as_of_date: str
    price_basis: PriceBasis
    fiscal_context: FiscalContext = Field(default_factory=FiscalContext)
    next_events: EventInfo = Field(default_factory=EventInfo)
    source_registry_id: str
    forward_eps: Optional[ForwardEPS] = None
    company_guidance_eps: Optional[CompanyGuidanceEPS] = None
