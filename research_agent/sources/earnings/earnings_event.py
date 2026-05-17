from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class EarningsEvent(BaseModel):
    ticker: str
    fiscal_period: Optional[str] = None
    report_date: str
    timing: Optional[str] = None
    confirmed: bool
    source_id: str
    source_type: str = "earnings_calendar"
    url: Optional[str] = None
    retrieved_at: Optional[str] = None
