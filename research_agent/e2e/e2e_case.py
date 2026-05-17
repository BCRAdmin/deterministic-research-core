from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ExpectedIssue(BaseModel):
    code: str
    severity: Optional[str] = None
    metric: Optional[str] = None
    must_find: bool = True


class ExpectedRatingCorridor(BaseModel):
    preferred_rating: Optional[str] = None
    allowed_ratings: List[str] = Field(default_factory=list)
    blocked_ratings: List[str] = Field(default_factory=list)


class E2ECase(BaseModel):
    case_id: str
    ticker: str
    as_of_date: str
    original_report_path: str
    data_packet_path: Optional[str] = None
    metrics_packet_path: Optional[str] = None
    validation_report_path: Optional[str] = None
    source_registry_path: Optional[str] = None
    evidence_ledger_path: Optional[str] = None
    decision_packet_path: Optional[str] = None
    expected_issues: List[ExpectedIssue] = Field(default_factory=list)
    expected_rating: ExpectedRatingCorridor = Field(default_factory=ExpectedRatingCorridor)
    minimum_quality_score: float = 85.0
    expected_final_status: str = "publishable"
    notes: Optional[str] = None
    metadata: Dict[str, object] = Field(default_factory=dict)
