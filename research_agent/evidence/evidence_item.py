from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


ClaimType = Literal[
    "financial_metric",
    "technical_metric",
    "valuation_metric",
    "guidance",
    "event",
    "news",
    "analyst_opinion",
    "price_data",
    "risk",
    "management_quote",
]


class EvidenceItem(BaseModel):
    evidence_id: str
    ticker: str
    claim_type: ClaimType
    source_id: str
    source_type: str
    authority_rank: int
    statement: str
    value: Optional[float] = None
    unit: Optional[str] = None
    period: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None
    retrieved_at: Optional[str] = None
    supports_metrics: List[str] = Field(default_factory=list)
    supports_claims: List[str] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
