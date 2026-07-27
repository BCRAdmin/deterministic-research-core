from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ResearchClaim(BaseModel):
    claim_id: Optional[str] = None
    section: Optional[str] = None
    claim_type: Optional[str] = None
    agent: str
    claim: str
    claim_text: Optional[str] = None
    evidence_metrics: List[str]
    metric_refs: List[str] = Field(default_factory=list)
    metric_values: Dict[str, float] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    source_ids: List[str]
    confidence: str
    importance: Optional[str] = None
    counterargument: Optional[str] = None
    investment_implication: Optional[str] = None
