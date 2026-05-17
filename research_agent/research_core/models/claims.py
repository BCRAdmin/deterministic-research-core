from typing import List, Optional

from pydantic import BaseModel


class ResearchClaim(BaseModel):
    claim_id: Optional[str] = None
    section: Optional[str] = None
    claim_type: Optional[str] = None
    agent: str
    claim: str
    claim_text: Optional[str] = None
    evidence_metrics: List[str]
    metric_refs: List[str] = []
    evidence_ids: List[str] = []
    source_ids: List[str]
    confidence: str
    importance: Optional[str] = None
    counterargument: Optional[str] = None
    investment_implication: Optional[str] = None
