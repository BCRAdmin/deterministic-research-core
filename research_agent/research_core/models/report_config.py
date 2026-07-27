from typing import Dict, Optional

from pydantic import BaseModel, Field


class FCFDefinitionConfig(BaseModel):
    formula_id: str = "cfo_minus_capex"
    subtract_capex: bool = True
    subtract_finance_lease_principal_payments: bool = False
    company_adjustments: float = 0.0
    metadata: Dict[str, object] = Field(default_factory=dict)


class ReportConfig(BaseModel):
    ticker: str
    as_of_date: str
    source_mode: str = "manual_packet_mode"
    fcf_definition: FCFDefinitionConfig = Field(default_factory=FCFDefinitionConfig)
    block_on_validation_errors: bool = True
    batch_mode: str = "current_research"
    freshness_reference_date: Optional[str] = None
    freshness_max_trading_days: int = 2
    output_dir: str = "research_agent/data/outputs"
    packet_dir: str = "research_agent/data/packets"
    price_csv_dir: Optional[str] = None
    price_start_date: Optional[str] = None
    price_source_id: Optional[str] = None
    price_source_type: str = "exchange_ohlcv"
    price_source_url: Optional[str] = None
    price_retrieved_at: Optional[str] = None
    price_currency: str = "USD"
    cik_records_path: Optional[str] = None
    sec_companyfacts_path: Optional[str] = None
    sec_user_agent: Optional[str] = None
    earnings_calendar_path: Optional[str] = None
    ir_release_dir: Optional[str] = None
    official_news_dir: Optional[str] = None
