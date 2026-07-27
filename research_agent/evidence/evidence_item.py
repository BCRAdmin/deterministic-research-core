from __future__ import annotations

from typing import Dict, List, Literal, Optional

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
    formula_id: Optional[str] = None
    formula_operands: Dict[str, float] = Field(default_factory=dict)
    raw_value: Optional[float] = None
    normalized_value: Optional[float] = None
    source_lineage: List[str] = Field(default_factory=list)
    duration_days: Optional[int] = None
    audited: Optional[bool] = None
    amendment_status: Optional[str] = None
